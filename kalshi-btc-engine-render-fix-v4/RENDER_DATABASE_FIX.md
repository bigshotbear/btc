# Render database driver fix

The application uses SQLAlchemy's asynchronous PostgreSQL engine and therefore requires the `asyncpg` driver.

The configuration now automatically converts all of these URL prefixes:

- `postgresql://`
- `postgres://`
- `postgresql+psycopg2://`
- `postgresql+psycopg://`
- `postgresql+pg8000://`

into:

- `postgresql+asyncpg://`

## Immediate Render workaround

In the Render web service Environment page, edit `DATABASE_URL` and replace only the URL prefix with `postgresql+asyncpg://`. Do not change the username, password, host, port, or database name.

Then use **Manual Deploy -> Clear build cache & deploy**.

## Preferred permanent fix

Upload this repository revision to GitHub and redeploy. The application will normalize the driver automatically.
