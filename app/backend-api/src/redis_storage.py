"""
Redis & Upstash Persistent Storage Provider (`StatelessRedisSession`)
Enables distributed, low-latency key-value and hash-based persistence for stateless
and serverless container deployments (e.g., Google Cloud Run, AWS Lambda).
"""

import json
import logging
import os
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger("daa.redis_storage")


class UpstashRestClient:
    """Minimal HTTP REST client for Upstash Redis when running over stateless REST APIs."""

    def __init__(self, rest_url: str, rest_token: str):
        self.rest_url = rest_url.rstrip("/")
        self.rest_token = rest_token

    def _execute(self, command: List[Any]) -> Any:
        url = self.rest_url
        headers = {
            "Authorization": f"Bearer {self.rest_token}",
            "Content-Type": "application/json",
        }
        data = json.dumps(command).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("result")
        except Exception as e:
            logger.error(f"Upstash REST API error for command {command[0]}: {e}")
            raise

    def get(self, key: str) -> Optional[str]:
        return self._execute(["GET", key])

    def set(self, key: str, value: str) -> Any:
        return self._execute(["SET", key, value])

    def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return self._execute(["DEL", *keys]) or 0

    def sadd(self, key: str, *members: str) -> int:
        if not members:
            return 0
        return self._execute(["SADD", key, *members]) or 0

    def srem(self, key: str, *members: str) -> int:
        if not members:
            return 0
        return self._execute(["SREM", key, *members]) or 0

    def smembers(self, key: str) -> set:
        res = self._execute(["SMEMBERS", key])
        return set(res) if res else set()


class RedisBackend:
    """Singleton connection manager for Redis / Upstash / In-Memory fallback."""

    _instance = None

    def __init__(self):
        self.client = None
        self.is_memory_fallback = False
        self._memory_store: Dict[str, Any] = {}
        self._memory_sets: Dict[str, set] = {}

        provider = os.environ.get("DAA_DB_PROVIDER", "").lower()
        upstash_url = os.environ.get("UPSTASH_REDIS_REST_URL")
        upstash_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        redis_url = os.environ.get("REDIS_URL") or os.environ.get("DAA_REDIS_URL")

        if provider == "upstash" or (upstash_url and upstash_token):
            if upstash_url and upstash_token:
                logger.info("Initializing Upstash REST client for Redis storage.")
                self.client = UpstashRestClient(upstash_url, upstash_token)
                return
            else:
                logger.warning("Upstash provider specified but UPSTASH_REDIS_REST_URL/TOKEN not set.")

        # Attempt standard redis-py client
        try:
            import redis
            if redis_url:
                self.client = redis.Redis.from_url(redis_url, decode_responses=True)
            else:
                host = os.environ.get("REDIS_HOST", "localhost")
                port = int(os.environ.get("REDIS_PORT", 6379))
                self.client = redis.Redis(host=host, port=port, decode_responses=True)
            # Quick ping check if local
            self.client.ping()
            logger.info("Connected to Redis storage backend successfully.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis server ({e}). Falling back to in-memory store for session.")
            self.client = None
            self.is_memory_fallback = True

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RedisBackend()
        return cls._instance

    def get(self, key: str) -> Optional[str]:
        if self.client:
            return self.client.get(key)
        return self._memory_store.get(key)

    def set(self, key: str, value: str) -> Any:
        if self.client:
            return self.client.set(key, value)
        self._memory_store[key] = value
        return True

    def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        if self.client:
            return self.client.delete(*keys)
        count = 0
        for k in keys:
            if k in self._memory_store:
                del self._memory_store[k]
                count += 1
        return count

    def sadd(self, key: str, *members: str) -> int:
        if not members:
            return 0
        if self.client:
            return self.client.sadd(key, *members)
        s = self._memory_sets.setdefault(key, set())
        initial_len = len(s)
        s.update(members)
        return len(s) - initial_len

    def srem(self, key: str, *members: str) -> int:
        if not members:
            return 0
        if self.client:
            return self.client.srem(key, *members)
        if key not in self._memory_sets:
            return 0
        s = self._memory_sets[key]
        initial_len = len(s)
        s.difference_update(members)
        return initial_len - len(s)

    def smembers(self, key: str) -> set:
        if self.client:
            res = self.client.smembers(key)
            return set(res) if res else set()
        return set(self._memory_sets.get(key, set()))


def _serialize_value(val: Any) -> Any:
    if isinstance(val, datetime):
        return val.isoformat()
    return val


def _deserialize_value(val: Any, target_type: Optional[Type] = None) -> Any:
    if isinstance(val, str) and (target_type == datetime or (val.count("-") == 2 and "T" in val)):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            pass
    return val


class RedisQuery:
    """ORM-compatible query adapter that executes lookups against Redis/Upstash hashes and sets."""

    def __init__(self, model_class: Type, backend: RedisBackend, pending_instances: Optional[List[Any]] = None):
        self.model_class = model_class
        self.backend = backend
        self.table_name = getattr(model_class, "__tablename__", model_class.__name__.lower())
        self._filters_args: List[Any] = []
        self._filters_kwargs: Dict[str, Any] = {}
        self._order_by_attr = None
        self._order_desc = False
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = 0
        self.pending_instances = pending_instances or []

    def filter(self, *args, **kwargs):
        self._filters_args.extend(args)
        self._filters_kwargs.update(kwargs)
        return self

    def filter_by(self, *args, **kwargs):
        self._filters_kwargs.update(kwargs)
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        if args:
            attr = args[0]
            if hasattr(attr, "element") and hasattr(attr, "modifier"):
                # e.g., Model.timestamp.desc()
                self._order_by_attr = getattr(attr.element, "key", str(attr.element))
                self._order_desc = (attr.modifier == "desc" or "desc" in str(attr).lower())
            elif hasattr(attr, "key"):
                self._order_by_attr = attr.key
                self._order_desc = False
            elif isinstance(attr, str):
                self._order_by_attr = attr
        return self

    def limit(self, val: int):
        self._limit_val = val
        return self

    def offset(self, val: int):
        self._offset_val = val
        return self

    def _matches_criteria(self, instance: Any) -> bool:
        # Check keyword arguments (`filter_by`)
        for key, expected in self._filters_kwargs.items():
            actual = getattr(instance, key, None)
            if actual != expected:
                return False

        # Check binary expressions (`filter`)
        for arg in self._filters_args:
            # Handle SQLAlchemy binary expression (e.g. Model.attr == val)
            if hasattr(arg, "left") and hasattr(arg, "right"):
                left_key = getattr(arg.left, "key", None) or getattr(arg.left, "name", None)
                right_val = getattr(arg.right, "value", arg.right)
                if hasattr(right_val, "value"):
                    right_val = right_val.value
                
                op_str = str(arg.operator.__name__) if hasattr(arg, "operator") else "eq"
                actual = getattr(instance, left_key, None) if left_key else None

                if op_str in ("eq", "__eq__", "eq_"):
                    if actual != right_val:
                        return False
                elif op_str in ("ne", "__ne__", "ne_"):
                    if actual == right_val:
                        return False
                elif op_str in ("in_op", "in_"):
                    if actual not in right_val:
                        return False
            elif callable(arg):
                if not arg(instance):
                    return False
        return True

    def _load_instance_from_data(self, data_json: str) -> Any:
        raw_dict = json.loads(data_json)
        instance = self.model_class()
        table_cols = getattr(getattr(self.model_class, "__table__", None), "columns", {})
        for col_name, val in raw_dict.items():
            if hasattr(self.model_class, col_name):
                col_type = None
                if col_name in table_cols:
                    col_obj = table_cols[col_name]
                    if hasattr(col_obj, "type") and hasattr(col_obj.type, "python_type"):
                        try:
                            col_type = col_obj.type.python_type
                        except Exception:
                            pass
                setattr(instance, col_name, _deserialize_value(val, col_type))
        return instance

    def _fetch_all_candidates(self) -> List[Any]:
        candidates: Dict[str, Any] = {}

        # First, load all persisted IDs from Redis index
        idx_key = f"daa:idx:{self.table_name}:all"
        ids = self.backend.smembers(idx_key)
        for doc_id in ids:
            record_key = f"daa:{self.table_name}:{doc_id}"
            data = self.backend.get(record_key)
            if data:
                try:
                    inst = self._load_instance_from_data(data)
                    inst_id = getattr(inst, "id", doc_id)
                    candidates[inst_id] = inst
                except Exception as e:
                    logger.warning(f"Failed to deserialize record {record_key}: {e}")

        # Merge in any pending uncommitted/modified instances in the session
        for inst in self.pending_instances:
            if isinstance(inst, self.model_class):
                inst_id = getattr(inst, "id", None)
                if inst_id:
                    candidates[inst_id] = inst

        # Filter candidates by criteria
        matched = [inst for inst in candidates.values() if self._matches_criteria(inst)]

        # Apply ordering if requested
        if self._order_by_attr:
            matched.sort(
                key=lambda x: getattr(x, self._order_by_attr, "") or "",
                reverse=self._order_desc,
            )
        else:
            # Default ordering by id or timestamp for stable ordering
            if hasattr(self.model_class, "timestamp"):
                matched.sort(key=lambda x: getattr(x, "timestamp", datetime.min) or datetime.min, reverse=True)

        return matched

    def first(self) -> Any:
        results = self._fetch_all_candidates()
        start = self._offset_val or 0
        if start < len(results):
            return results[start]
        return None

    def all(self) -> List[Any]:
        results = self._fetch_all_candidates()
        start = self._offset_val or 0
        end = start + self._limit_val if self._limit_val is not None else len(results)
        return results[start:end]

    def count(self) -> int:
        return len(self._fetch_all_candidates())


class StatelessRedisSession:
    """
    Drop-in SQLAlchemy Session replacement backed by Redis/Upstash.
    Provides persistent record storage (`add`, `delete`, `commit`, `query`) across stateless containers.
    """

    def __init__(self, *args, **kwargs):
        self.backend = RedisBackend.get_instance()
        self.dirty_instances: List[Any] = []
        self.deleted_instances: List[Any] = []

    def query(self, model_class: Type) -> RedisQuery:
        return RedisQuery(model_class, self.backend, pending_instances=self.dirty_instances)

    def add(self, instance: Any):
        if hasattr(instance, "id") and not getattr(instance, "id"):
            instance.id = str(uuid.uuid4())
        if hasattr(instance, "timestamp") and not getattr(instance, "timestamp"):
            instance.timestamp = datetime.utcnow()
        if hasattr(instance, "created_at") and not getattr(instance, "created_at"):
            instance.created_at = datetime.utcnow()
        if hasattr(instance, "first_seen_at") and not getattr(instance, "first_seen_at"):
            instance.first_seen_at = datetime.utcnow()
        if hasattr(instance, "last_seen_at") and not getattr(instance, "last_seen_at"):
            instance.last_seen_at = datetime.utcnow()

        if instance not in self.dirty_instances:
            self.dirty_instances.append(instance)

    def delete(self, instance: Any):
        if instance in self.dirty_instances:
            self.dirty_instances.remove(instance)
        if instance not in self.deleted_instances:
            self.deleted_instances.append(instance)

    def commit(self):
        # 1. Process deletions
        for inst in self.deleted_instances:
            inst_id = getattr(inst, "id", None)
            if not inst_id:
                continue
            table_name = getattr(inst, "__tablename__", type(inst).__name__.lower())
            record_key = f"daa:{table_name}:{inst_id}"
            idx_key = f"daa:idx:{table_name}:all"
            self.backend.delete(record_key)
            self.backend.srem(idx_key, str(inst_id))
        self.deleted_instances.clear()

        # 2. Process additions and modifications
        for inst in self.dirty_instances:
            inst_id = getattr(inst, "id", None)
            if not inst_id:
                continue
            table_name = getattr(inst, "__tablename__", type(inst).__name__.lower())
            record_key = f"daa:{table_name}:{inst_id}"
            idx_key = f"daa:idx:{table_name}:all"

            # Serialize model fields to dict
            payload = {}
            if hasattr(inst, "__table__"):
                for col in inst.__table__.columns:
                    val = getattr(inst, col.name, None)
                    payload[col.name] = _serialize_value(val)
            else:
                for col_name in dir(inst):
                    if col_name.startswith("_") or col_name in ("metadata", "registry") or callable(getattr(inst, col_name)):
                        continue
                    val = getattr(inst, col_name)
                    try:
                        json.dumps(_serialize_value(val))
                        payload[col_name] = _serialize_value(val)
                    except (TypeError, OverflowError):
                        pass

            data_json = json.dumps(payload)
            self.backend.set(record_key, data_json)
            self.backend.sadd(idx_key, str(inst_id))
        self.dirty_instances.clear()

    def rollback(self):
        self.dirty_instances.clear()
        self.deleted_instances.clear()

    def refresh(self, instance: Any):
        inst_id = getattr(instance, "id", None)
        if not inst_id:
            return
        table_name = getattr(instance, "__tablename__", type(instance).__name__.lower())
        record_key = f"daa:{table_name}:{inst_id}"
        data = self.backend.get(record_key)
        if data:
            raw_dict = json.loads(data)
            for col_name, val in raw_dict.items():
                if hasattr(instance, col_name):
                    setattr(instance, col_name, _deserialize_value(val))

    def close(self):
        pass

    def begin(self):
        class TransactionContext:
            def __init__(self, session):
                self.session = session

            def __enter__(self):
                return self.session

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is not None:
                    self.session.rollback()
                else:
                    self.session.commit()

        return TransactionContext(self)
