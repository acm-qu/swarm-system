# data/

The hub keeps its private runtime files here. Everything in this folder except this README is
gitignored. Never commit these files.

| File              | What it is                                                       |
|-------------------|------------------------------------------------------------------|
| `users.json`      | Hub logins (password hashes). Create with `python -m hub adduser`. |
| `.secret_key`     | Signs the login cookie.                                          |
| `robot_token.txt` | Shared secret robots send when they connect.                     |
| `hub_ssh_key`     | The hub's SSH key; every robot it installs trusts it.            |
| `robots.json`     | Robots this hub has installed (address, user, SSH host key).     |

All but `users.json` are created automatically on first run. To keep them somewhere else, set
`SWARM_DATA_DIR`. To replace the keys, see `python -m hub rotate` in the main README.
