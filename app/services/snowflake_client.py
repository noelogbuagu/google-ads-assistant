import asyncio
import base64
import os

import snowflake.connector
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_der_private_key,
    load_pem_private_key,
)


def _load_private_key(key_bytes: bytes, passphrase: str | None):
    password = passphrase.encode() if passphrase else None
    if key_bytes.lstrip().startswith(b"-----"):
        return load_pem_private_key(key_bytes, password=password)
    return load_der_private_key(key_bytes, password=password)


def get_snowflake_connection():
    key_bytes = base64.b64decode(os.environ["SNOWFLAKE_PRIVATE_KEY_B64"])
    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    private_key = _load_private_key(key_bytes, passphrase)
    pkb = private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=pkb,
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ.get("SNOWFLAKE_DATABASE", "DWH"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "MARKETING"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )


async def run_query(sql: str, params: dict) -> list[dict]:
    def _run():
        conn = get_snowflake_connection()
        try:
            cur = conn.cursor(snowflake.connector.DictCursor)
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    return await asyncio.to_thread(_run)
