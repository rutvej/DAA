import itertools

stagings = ['Image', 'Compose']
dbs = ['none', 'sqlite', 'postgres']
queues = ['sync', 'rabbitmq']
gits = ['api', 'local']
auths = ['true', 'false']
policies = ['true', 'false']
integrations = ['SDK', 'Non-SDK']

combinations = list(itertools.product(stagings, dbs, queues, gits, auths, policies, integrations))

with open('matrix.md', 'w') as f:
    f.write("# DAA Combinations Matrix (with SQLite)\n\n")
    f.write("| # | Staging | DB | Queue | Git | Auth | Policy | Integration | Expected Outcome | Reason |\n")
    f.write("|---|---|---|---|---|---|---|---|---|---|\n")
    
    valid_count = 0
    invalid_count = 0
    
    for i, c in enumerate(combinations):
        staging, db, queue, git, auth, policy, integration = c
        
        outcome = "✅ Works"
        reason = "Valid configuration."
        
        # Evaluate constraints
        if staging == 'Image' and git == 'local':
            outcome = "❌ Fails"
            reason = "Cloud Run (Image) lacks Docker socket required for 'local' testing."
        elif db == 'none' and (auth == 'true' or policy == 'true'):
            outcome = "❌ Fails"
            reason = "Stateless mode (no DB) cannot enforce Auth/Tokens or store HITL Policies."
        elif db == 'none' and queue == 'rabbitmq':
            outcome = "❌ Fails"
            reason = "Async jobs (MQ) require a DB to track incident/fix status across workers."
        elif db == 'none' and integration == 'SDK' and auth == 'true':
            outcome = "❌ Fails"
            reason = "SDK requires token validation, which fails without a DB."
        elif db == 'sqlite' and staging == 'Compose':
            outcome = "❌ Fails"
            reason = "Compose deploys API and Agent as separate containers. SQLite is a local file, so log_query_tool will query an empty DB in the agent container."
        
        if outcome == "✅ Works":
            valid_count += 1
        else:
            invalid_count += 1
            
        f.write(f"| {i+1} | {staging} | {db} | {queue} | {git} | {auth} | {policy} | {integration} | {outcome} | {reason} |\n")
    
    f.write(f"\n\n**Summary:** {valid_count} Valid, {invalid_count} Invalid\n")

