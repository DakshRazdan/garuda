import hmac
import hashlib
import os

SECRET = os.environ.get("GARUDA_HMAC_SECRET", "dev-secret-change-me").encode()


def sign(batch_id: str, row_hash: str, nfc_tag_uid: str) -> str:
    payload = f"{batch_id}|{row_hash}|{nfc_tag_uid}".encode()
    return hmac.new(SECRET, payload, hashlib.sha256).hexdigest()


def verify(batch_id: str, row_hash: str, nfc_tag_uid: str, signature: str) -> bool:
    if not signature:
        return False
    expected = sign(batch_id, row_hash, nfc_tag_uid)
    return hmac.compare_digest(expected, signature)
