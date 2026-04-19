# Solidity Fee Flow

Fee settlement to avoid accounting drift must call `collectProtocolFees` before treasury transfer.

For each `PoolId`, validate basis points, keep 0.3% constants unchanged.

Do not rename contract interface identifiers.
