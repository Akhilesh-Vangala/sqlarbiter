"""Signed, expiring anonymous demo envelopes; no shared serverless history."""

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import HTTPException


class DemoSession:
    def __init__(self, secret, cookie):
        if len(secret) < 48:
            raise ValueError(
                "Public demo requires a private signing secret of at least48characters"
            )
        self.key, self.cookie = secret.encode(), cookie

    def seal(self, value, purpose):
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        signature = hmac.new(
            self.key, (purpose + ":" + payload).encode(), hashlib.sha256
        ).hexdigest()
        return payload + "." + signature

    def open(self, token, purpose):
        if not isinstance(token, str) or len(token) > 18000:
            raise HTTPException(400, "Invalid demo envelope")
        try:
            payload, signature = token.split(".")
            expected = hmac.new(
                self.key, (purpose + ":" + payload).encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            value = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            if type(value.get("expires")) is not int or value["expires"] <= time.time():
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                409, "Demo state is invalid or expired; start a new investigation"
            ) from None
        return value

    def visitor(self, request, response=None):
        token = request.cookies.get(self.cookie)
        if token:
            try:
                return self.open(token, "visitor")["id"]
            except (HTTPException, KeyError):
                pass
        if response is None:
            raise HTTPException(401, "Open the demo workspace before running an action")
        identity = secrets.token_hex(24)
        response.set_cookie(
            self.cookie,
            self.seal({"id": identity, "expires": int(time.time()) + 3600}, "visitor"),
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="strict",
            max_age=3600,
        )
        return identity

    def issue(self, state, visitor):
        return self.seal(
            {**state, "visitor": visitor, "expires": int(time.time()) + 1800}, "workflow"
        )

    def consume(self, request, token):
        state = self.open(token, "workflow")
        if not hmac.compare_digest(state.get("visitor", ""), self.visitor(request)):
            raise HTTPException(403, "Demo state belongs to a different browser session")
        return state
