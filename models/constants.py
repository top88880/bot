"""Shared constants for the bot application."""

# Inventory states (integer based)
STATE_AVAILABLE = 0  # Product is available for sale
STATE_SOLD = 1       # Product has been sold

# Tenant types
TENANT_MASTER = "master"
TENANT_AGENT_PREFIX = "agent:"

# Order/Sale statuses
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_SUCCESS = "success"
ORDER_STATUS_CANCELLED = "cancelled"
ORDER_STATUS_EXPIRED = "expired"

# Topup/Recharge statuses
TOPUP_STATUS_PENDING = "pending"
TOPUP_STATUS_SUCCESS = "success"
TOPUP_STATUS_CANCELLED = "cancelled"
TOPUP_STATUS_EXPIRED = "expired"

# Agent statuses
AGENT_STATUS_ACTIVE = "active"
AGENT_STATUS_PAUSED = "paused"
AGENT_STATUS_SUSPENDED = "suspended"

# Ledger statuses
LEDGER_STATUS_PENDING = "pending"    # Profit not yet matured
LEDGER_STATUS_MATURED = "matured"    # Profit available for withdrawal
LEDGER_STATUS_WITHDRAWN = "withdrawn"  # Profit has been withdrawn
LEDGER_STATUS_REVERTED = "reverted"  # Transaction was refunded

# Withdrawal statuses
WITHDRAWAL_STATUS_REQUESTED = "requested"  # Agent requested withdrawal
WITHDRAWAL_STATUS_APPROVED = "approved"    # Admin approved, awaiting payment
WITHDRAWAL_STATUS_PAID = "paid"            # Admin marked as paid with TXID
WITHDRAWAL_STATUS_REJECTED = "rejected"    # Admin rejected the request

# Ledger entry types
LEDGER_TYPE_SALE = "sale"
LEDGER_TYPE_REFUND = "refund"

# Sold by types
SOLD_BY_MASTER = "master"
SOLD_BY_AGENT = "agent"

# Pricing markup types
MARKUP_TYPE_FIXED = "fixed"      # Fixed amount per item
MARKUP_TYPE_PERCENT = "percent"  # Percentage of base price

# Maturity window (in hours)
PROFIT_MATURITY_HOURS = 48

# Default markup values
DEFAULT_MARKUP_PERCENT = 0
DEFAULT_MARKUP_FIXED = 0
