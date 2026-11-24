# Protocol and code provenance

`crypto.py` is adapted from the MIT-licensed `ninebot_crypto.py` in
[kxn/ninebot-recon](https://github.com/kxn/ninebot-recon), pinned at
`5f4f200122b0e2769bdd7d89ba56f7e258728689`. Original copyright and license
are retained in `LICENSE.kxn`. Local changes remove executable self-tests and
unused imports, format the source, and handle typed RSA key loading. No upstream
binary or native library is distributed or executed.

The request profile was checked against a user-supplied official domestic
Segway-Ninebot 6.10.13 Android APK and successful user-authorized password login,
business login and vehicle queries on 2026-11-13. Android Passport v6 is used;
the iOS Passport v3 request encryption is not copied or required.

Static APK inspection confirms Passport success 90000, the /v3/user/refresh
snake_case fields, the boolean conversion helper, total_mileage in km (feature_core_1.json),
lastupdatetime in seconds, and WGS84 input into the App's
gps84_To_Gcj02 map conversion. Lock enum and business expiry codes beyond known
HTTP 401 / SDK 90016 remain unconfirmed. No secret captured material is included.

Constants called clientKey and the RSA public key are protocol public client
material, not the user's account credentials. Personal passwords and tokens
are never embedded in source.

The v0.2.0 information inventory, cycle-support semantics and adaptive polling idea
were checked against Wuty-zju/ha_ninebot (MIT), pinned at
`d1fba4bdc92fbe9f13cf0555d7eca953b8fb5b01`.
This project's battery projection and scheduling are independently implemented;
no ninecli executable or upstream control/history/AI code is included.
The battery-info POST route on ebike.ninebot.com was present in the user's prior
authorized App capture and successfully replayed with this client's profile on
2026-11-24. The live check exported only allowlisted measurements and request
phases, without credentials, vehicle identifiers or coordinates; see docs/VERIFICATION.md.
