"""Pinned protocol vectors; independent of network and personal captures."""

import base64
import json

from custom_components.ninebot_connect import crypto


def test_fixed_derive_key_vector():
    assert (
        crypto.derive_key(b"abcdefghijklm", b"0123456789ab", b"XYZ", b"ninebot!").hex()
        == "82ffe6a8cbb9a4ffdbf791a74e37176e"
    )


def test_android_base64_and_checkcode_vectors():
    assert crypto.android_b64(b"a") == "YQ==\n"
    assert crypto.build_inner({"x": 1}) == '{"x":1,"checkcode":"AC3EF48CAA08FA3ED5E025DA69EDC645"}'


def test_response_aes_and_wrapper_roundtrip():
    material = {"kd1": "test-one", "kd2": "test-two", "kd3": "test-three", "kd4": "test-four"}
    key = crypto.derive_key(*(v.encode() for v in material.values()))
    plain = json.dumps({"data": base64.b64encode(b'{"code":1,"data":[]}').decode()}).encode()
    encrypted = crypto._aes_cbc_encrypt(key, plain)
    assert (
        crypto.decrypt_wire_response({"r": base64.b64encode(encrypted).decode()}, material)
        == b'{"code":1,"data":[]}'
    )


def test_aes_fixed_nist_first_block():
    # NIST SP800-38A F.2.1, IV=0 achieved by xor-ing the standard IV into the plaintext.
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    plain = bytes(
        a ^ b
        for a, b in zip(
            bytes.fromhex("6bc1bee22e409f96e93d7e117393172a"), bytes(range(16)), strict=True
        )
    )
    assert crypto._aes_cbc_encrypt(key, plain)[:16].hex() == "7649abac8119b246cee98e9b12e9197d"
