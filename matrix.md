# DAA Combinations Matrix (with SQLite)

| # | Staging | DB | Queue | Git | Auth | Policy | Integration | Expected Outcome | Reason |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Image | none | sync | api | true | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 2 | Image | none | sync | api | true | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 3 | Image | none | sync | api | true | false | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 4 | Image | none | sync | api | true | false | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 5 | Image | none | sync | api | false | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 6 | Image | none | sync | api | false | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 7 | Image | none | sync | api | false | false | SDK | ✅ Works | Valid configuration. |
| 8 | Image | none | sync | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 9 | Image | none | sync | local | true | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 10 | Image | none | sync | local | true | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 11 | Image | none | sync | local | true | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 12 | Image | none | sync | local | true | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 13 | Image | none | sync | local | false | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 14 | Image | none | sync | local | false | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 15 | Image | none | sync | local | false | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 16 | Image | none | sync | local | false | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 17 | Image | none | rabbitmq | api | true | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 18 | Image | none | rabbitmq | api | true | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 19 | Image | none | rabbitmq | api | true | false | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 20 | Image | none | rabbitmq | api | true | false | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 21 | Image | none | rabbitmq | api | false | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 22 | Image | none | rabbitmq | api | false | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 23 | Image | none | rabbitmq | api | false | false | SDK | ❌ Fails | Async jobs (MQ) require a DB to track incident/fix status across workers. |
| 24 | Image | none | rabbitmq | api | false | false | Non-SDK | ❌ Fails | Async jobs (MQ) require a DB to track incident/fix status across workers. |
| 25 | Image | none | rabbitmq | local | true | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 26 | Image | none | rabbitmq | local | true | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 27 | Image | none | rabbitmq | local | true | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 28 | Image | none | rabbitmq | local | true | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 29 | Image | none | rabbitmq | local | false | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 30 | Image | none | rabbitmq | local | false | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 31 | Image | none | rabbitmq | local | false | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 32 | Image | none | rabbitmq | local | false | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 33 | Image | sqlite | sync | api | true | true | SDK | ✅ Works | Valid configuration. |
| 34 | Image | sqlite | sync | api | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 35 | Image | sqlite | sync | api | true | false | SDK | ✅ Works | Valid configuration. |
| 36 | Image | sqlite | sync | api | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 37 | Image | sqlite | sync | api | false | true | SDK | ✅ Works | Valid configuration. |
| 38 | Image | sqlite | sync | api | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 39 | Image | sqlite | sync | api | false | false | SDK | ✅ Works | Valid configuration. |
| 40 | Image | sqlite | sync | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 41 | Image | sqlite | sync | local | true | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 42 | Image | sqlite | sync | local | true | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 43 | Image | sqlite | sync | local | true | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 44 | Image | sqlite | sync | local | true | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 45 | Image | sqlite | sync | local | false | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 46 | Image | sqlite | sync | local | false | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 47 | Image | sqlite | sync | local | false | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 48 | Image | sqlite | sync | local | false | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 49 | Image | sqlite | rabbitmq | api | true | true | SDK | ✅ Works | Valid configuration. |
| 50 | Image | sqlite | rabbitmq | api | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 51 | Image | sqlite | rabbitmq | api | true | false | SDK | ✅ Works | Valid configuration. |
| 52 | Image | sqlite | rabbitmq | api | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 53 | Image | sqlite | rabbitmq | api | false | true | SDK | ✅ Works | Valid configuration. |
| 54 | Image | sqlite | rabbitmq | api | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 55 | Image | sqlite | rabbitmq | api | false | false | SDK | ✅ Works | Valid configuration. |
| 56 | Image | sqlite | rabbitmq | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 57 | Image | sqlite | rabbitmq | local | true | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 58 | Image | sqlite | rabbitmq | local | true | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 59 | Image | sqlite | rabbitmq | local | true | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 60 | Image | sqlite | rabbitmq | local | true | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 61 | Image | sqlite | rabbitmq | local | false | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 62 | Image | sqlite | rabbitmq | local | false | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 63 | Image | sqlite | rabbitmq | local | false | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 64 | Image | sqlite | rabbitmq | local | false | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 65 | Image | postgres | sync | api | true | true | SDK | ✅ Works | Valid configuration. |
| 66 | Image | postgres | sync | api | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 67 | Image | postgres | sync | api | true | false | SDK | ✅ Works | Valid configuration. |
| 68 | Image | postgres | sync | api | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 69 | Image | postgres | sync | api | false | true | SDK | ✅ Works | Valid configuration. |
| 70 | Image | postgres | sync | api | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 71 | Image | postgres | sync | api | false | false | SDK | ✅ Works | Valid configuration. |
| 72 | Image | postgres | sync | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 73 | Image | postgres | sync | local | true | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 74 | Image | postgres | sync | local | true | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 75 | Image | postgres | sync | local | true | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 76 | Image | postgres | sync | local | true | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 77 | Image | postgres | sync | local | false | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 78 | Image | postgres | sync | local | false | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 79 | Image | postgres | sync | local | false | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 80 | Image | postgres | sync | local | false | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 81 | Image | postgres | rabbitmq | api | true | true | SDK | ✅ Works | Valid configuration. |
| 82 | Image | postgres | rabbitmq | api | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 83 | Image | postgres | rabbitmq | api | true | false | SDK | ✅ Works | Valid configuration. |
| 84 | Image | postgres | rabbitmq | api | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 85 | Image | postgres | rabbitmq | api | false | true | SDK | ✅ Works | Valid configuration. |
| 86 | Image | postgres | rabbitmq | api | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 87 | Image | postgres | rabbitmq | api | false | false | SDK | ✅ Works | Valid configuration. |
| 88 | Image | postgres | rabbitmq | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 89 | Image | postgres | rabbitmq | local | true | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 90 | Image | postgres | rabbitmq | local | true | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 91 | Image | postgres | rabbitmq | local | true | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 92 | Image | postgres | rabbitmq | local | true | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 93 | Image | postgres | rabbitmq | local | false | true | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 94 | Image | postgres | rabbitmq | local | false | true | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 95 | Image | postgres | rabbitmq | local | false | false | SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 96 | Image | postgres | rabbitmq | local | false | false | Non-SDK | ❌ Fails | Cloud Run (Image) lacks Docker socket required for 'local' testing. |
| 97 | Compose | none | sync | api | true | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 98 | Compose | none | sync | api | true | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 99 | Compose | none | sync | api | true | false | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 100 | Compose | none | sync | api | true | false | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 101 | Compose | none | sync | api | false | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 102 | Compose | none | sync | api | false | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 103 | Compose | none | sync | api | false | false | SDK | ✅ Works | Valid configuration. |
| 104 | Compose | none | sync | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 105 | Compose | none | sync | local | true | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 106 | Compose | none | sync | local | true | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 107 | Compose | none | sync | local | true | false | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 108 | Compose | none | sync | local | true | false | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 109 | Compose | none | sync | local | false | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 110 | Compose | none | sync | local | false | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 111 | Compose | none | sync | local | false | false | SDK | ✅ Works | Valid configuration. |
| 112 | Compose | none | sync | local | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 113 | Compose | none | rabbitmq | api | true | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 114 | Compose | none | rabbitmq | api | true | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 115 | Compose | none | rabbitmq | api | true | false | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 116 | Compose | none | rabbitmq | api | true | false | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 117 | Compose | none | rabbitmq | api | false | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 118 | Compose | none | rabbitmq | api | false | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 119 | Compose | none | rabbitmq | api | false | false | SDK | ❌ Fails | Async jobs (MQ) require a DB to track incident/fix status across workers. |
| 120 | Compose | none | rabbitmq | api | false | false | Non-SDK | ❌ Fails | Async jobs (MQ) require a DB to track incident/fix status across workers. |
| 121 | Compose | none | rabbitmq | local | true | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 122 | Compose | none | rabbitmq | local | true | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 123 | Compose | none | rabbitmq | local | true | false | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 124 | Compose | none | rabbitmq | local | true | false | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 125 | Compose | none | rabbitmq | local | false | true | SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 126 | Compose | none | rabbitmq | local | false | true | Non-SDK | ❌ Fails | Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies. |
| 127 | Compose | none | rabbitmq | local | false | false | SDK | ❌ Fails | Async jobs (MQ) require a DB to track incident/fix status across workers. |
| 128 | Compose | none | rabbitmq | local | false | false | Non-SDK | ❌ Fails | Async jobs (MQ) require a DB to track incident/fix status across workers. |
| 129 | Compose | sqlite | sync | api | true | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 130 | Compose | sqlite | sync | api | true | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 131 | Compose | sqlite | sync | api | true | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 132 | Compose | sqlite | sync | api | true | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 133 | Compose | sqlite | sync | api | false | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 134 | Compose | sqlite | sync | api | false | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 135 | Compose | sqlite | sync | api | false | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 136 | Compose | sqlite | sync | api | false | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 137 | Compose | sqlite | sync | local | true | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 138 | Compose | sqlite | sync | local | true | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 139 | Compose | sqlite | sync | local | true | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 140 | Compose | sqlite | sync | local | true | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 141 | Compose | sqlite | sync | local | false | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 142 | Compose | sqlite | sync | local | false | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 143 | Compose | sqlite | sync | local | false | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 144 | Compose | sqlite | sync | local | false | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 145 | Compose | sqlite | rabbitmq | api | true | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 146 | Compose | sqlite | rabbitmq | api | true | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 147 | Compose | sqlite | rabbitmq | api | true | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 148 | Compose | sqlite | rabbitmq | api | true | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 149 | Compose | sqlite | rabbitmq | api | false | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 150 | Compose | sqlite | rabbitmq | api | false | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 151 | Compose | sqlite | rabbitmq | api | false | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 152 | Compose | sqlite | rabbitmq | api | false | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 153 | Compose | sqlite | rabbitmq | local | true | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 154 | Compose | sqlite | rabbitmq | local | true | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 155 | Compose | sqlite | rabbitmq | local | true | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 156 | Compose | sqlite | rabbitmq | local | true | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 157 | Compose | sqlite | rabbitmq | local | false | true | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 158 | Compose | sqlite | rabbitmq | local | false | true | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 159 | Compose | sqlite | rabbitmq | local | false | false | SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 160 | Compose | sqlite | rabbitmq | local | false | false | Non-SDK | ❌ Fails | Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container. |
| 161 | Compose | postgres | sync | api | true | true | SDK | ✅ Works | Valid configuration. |
| 162 | Compose | postgres | sync | api | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 163 | Compose | postgres | sync | api | true | false | SDK | ✅ Works | Valid configuration. |
| 164 | Compose | postgres | sync | api | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 165 | Compose | postgres | sync | api | false | true | SDK | ✅ Works | Valid configuration. |
| 166 | Compose | postgres | sync | api | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 167 | Compose | postgres | sync | api | false | false | SDK | ✅ Works | Valid configuration. |
| 168 | Compose | postgres | sync | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 169 | Compose | postgres | sync | local | true | true | SDK | ✅ Works | Valid configuration. |
| 170 | Compose | postgres | sync | local | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 171 | Compose | postgres | sync | local | true | false | SDK | ✅ Works | Valid configuration. |
| 172 | Compose | postgres | sync | local | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 173 | Compose | postgres | sync | local | false | true | SDK | ✅ Works | Valid configuration. |
| 174 | Compose | postgres | sync | local | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 175 | Compose | postgres | sync | local | false | false | SDK | ✅ Works | Valid configuration. |
| 176 | Compose | postgres | sync | local | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 177 | Compose | postgres | rabbitmq | api | true | true | SDK | ✅ Works | Valid configuration. |
| 178 | Compose | postgres | rabbitmq | api | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 179 | Compose | postgres | rabbitmq | api | true | false | SDK | ✅ Works | Valid configuration. |
| 180 | Compose | postgres | rabbitmq | api | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 181 | Compose | postgres | rabbitmq | api | false | true | SDK | ✅ Works | Valid configuration. |
| 182 | Compose | postgres | rabbitmq | api | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 183 | Compose | postgres | rabbitmq | api | false | false | SDK | ✅ Works | Valid configuration. |
| 184 | Compose | postgres | rabbitmq | api | false | false | Non-SDK | ✅ Works | Valid configuration. |
| 185 | Compose | postgres | rabbitmq | local | true | true | SDK | ✅ Works | Valid configuration. |
| 186 | Compose | postgres | rabbitmq | local | true | true | Non-SDK | ✅ Works | Valid configuration. |
| 187 | Compose | postgres | rabbitmq | local | true | false | SDK | ✅ Works | Valid configuration. |
| 188 | Compose | postgres | rabbitmq | local | true | false | Non-SDK | ✅ Works | Valid configuration. |
| 189 | Compose | postgres | rabbitmq | local | false | true | SDK | ✅ Works | Valid configuration. |
| 190 | Compose | postgres | rabbitmq | local | false | true | Non-SDK | ✅ Works | Valid configuration. |
| 191 | Compose | postgres | rabbitmq | local | false | false | SDK | ✅ Works | Valid configuration. |
| 192 | Compose | postgres | rabbitmq | local | false | false | Non-SDK | ✅ Works | Valid configuration. |


**Summary:** 70 Valid, 122 Invalid
