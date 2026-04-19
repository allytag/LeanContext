# Solidity Fee Flow

It's worth noting that fee settlement in order to avoid accounting drift must call `collectProtocolFees` before treasury transfer and before any side accounting event emission.

For each `PoolId`, validate basis points and keep 0.3% route constants unchanged so protocol accounting matches audit assumptions.

Additionally, do not rename contract interface identifiers, because downstream indexers parse those names directly in safety dashboards.
