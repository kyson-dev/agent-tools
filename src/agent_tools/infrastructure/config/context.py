import contextvars

# Thread-safe and async-safe context variable for the repository path
REPO_CWD: contextvars.ContextVar[str | None] = contextvars.ContextVar("REPO_CWD", default=None)
