from collections.abc import Generator

import psycopg
from fastapi import Request
from psycopg.rows import dict_row


def get_connection(request: Request) -> Generator[psycopg.Connection, None, None]:
    settings = request.app.state.settings
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        yield connection
