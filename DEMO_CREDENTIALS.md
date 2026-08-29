# AITAM Demo Credentials

Local hackathon/demo credentials only. Do not use these passwords in
production, commit them into a public repository, or expose them through an
API response. Passwords are stored in `campusflow.db` only as hashes using the
existing authentication mechanism.

## Credentials

| Demo account | Username | Password | Existing login identifier | Role/scope |
|---|---|---|---|---|
| Admin | `admin` | `AITAM@Admin123` | `/api/v1/auth/login` with username `admin` | `operator` (existing privileged admin-equivalent) |
| Community user | `community` | `AITAM@User123` | `/api/v1/auth/login` with username `community` | `user` / Community |
| Security Department | `security` | `AITAM@Security123` | `/api/v1/auth/department/login` with `security@aitam.local`, department `SECURITY` | `department_head` / SECURITY |
| Medical Department | `medical` | `AITAM@Medical123` | `/api/v1/auth/department/login` with `medical@aitam.local`, department `MEDICAL` | `department_head` / MEDICAL |
| Search & Rescue Department | `rescue` | `AITAM@Rescue123` | `/api/v1/auth/department/login` with `rescue@aitam.local`, department `SEARCH_AND_RESCUE` | `department_head` / Search & Rescue |
| Fire Department | `fire` | `AITAM@Fire123` | `/api/v1/auth/department/login` with `fire@aitam.local`, department `FIRE` | `department_head` / FIRE |
| Transport Department | `transport` | `AITAM@Transport123` | `/api/v1/auth/department/login` with `transport@aitam.local`, department `TRANSPORT` | `department_head` / TRANSPORT |
| Communication Department | `communication` | `AITAM@Communication123` | `/api/v1/auth/department/login` with `communication@aitam.local`, department `COMMUNICATION` | `department_head` / COMMUNICATION |
| Infrastructure/Facilities Department | `facilities` | `AITAM@Facilities123` | `/api/v1/auth/department/login` with `facilities@aitam.local`, department `FACILITIES` | `department_head` / FACILITIES |
| Shelter & Relief Department | `shelter` | `AITAM@Shelter123` | `/api/v1/auth/department/login` with `shelter@aitam.local`, department `SHELTER` | `department_head` / SHELTER |

## Existing UI note

The current Community portal UI preserves the existing email + phone identity
flow. Its existing demo identity is `community@aitam.local` with phone
`9000000000`. The requested username/password credential above is verified
through the existing username login endpoint and does not remove or replace
the portal identity flow.

Department UI login uses the documented email and canonical department value;
the short usernames above are the local demo labels for those existing email
accounts.

The persisted organization registry now contains eight active operational
departments. The Search & Rescue and Shelter accounts are distinct department
scopes; existing 11.5B rescue data was migrated only from the old SECURITY
scope to `SEARCH_AND_RESCUE`.
