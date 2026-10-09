# Deployment options

**Default: local-first.** The audit runs where the data already are, makes no network calls
and uses no model.

| Option | Advantages | Disadvantages | Data movement | Security implications | Support burden |
|---|---|---|---|---|---|
| **Local workstation** (default; available now: `pip install`, CLI and Streamlit on 127.0.0.1) | no data transfer; fastest to start; customer keeps control; works offline | single user; no central audit trail across users; install on locked-down machines may need IT help; performance limited by the machine (about 2.4 GB RAM at 8 subjects) | none (only the outputs the customer chooses to share) | the customer's workstation controls apply; the app binds to localhost; bundles hold no images; paths pseudonymised | low to medium: installation and Python environment issues |
| **On-prem server** (possible with the current software; not packaged) | shared by a team; central storage of bundles and review logs; larger trials | needs server administration; the Streamlit app has **no authentication or role-based access** today, so it must sit behind the customer's access controls; concurrency not designed for | inside the customer network | requires the customer's network access control; review logs record self-entered reviewer IDs, not authenticated identities | medium: deployment, upgrades, backups |
| **Private cloud** (customer's own tenant; not available) | elastic compute; central access | data leave the on-prem environment, so DUA/DPA and security review are required; authentication, encryption and logging must be built first | customer storage → customer cloud | needs authentication, RBAC, encryption at rest and in transit, and logging (none built) | high |
| **Core-lab API** (not available) | integrates into core-lab pipelines; automatic on data arrival | no API exists; versioning, authentication and SLA needed; harder to validate | core-lab system → VoxelTrace service (in their environment) | service authentication, input validation, audit trail | high |

## Recommendation

- **Now:** local workstation (default) for pilots, with an optional on-prem server only
  behind the customer's own access controls.
- **Later:** cloud and API only after authentication, role-based access, signed releases and
  a security review exist (`release_gates.md`, gate 4).
