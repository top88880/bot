"""Tenant context utilities.

This module provides helpers for working with multi-tenant contexts.
"""

from models.constants import TENANT_MASTER, TENANT_AGENT_PREFIX


def get_tenant_string(agent_id: str = None) -> str:
    """Get the tenant string for a given agent.
    
    Args:
        agent_id: The agent ID. If None, returns master tenant.
    
    Returns:
        str: Tenant string ("master" or "agent:<agent_id>").
    """
    if agent_id is None:
        return TENANT_MASTER
    return f"{TENANT_AGENT_PREFIX}{agent_id}"


def parse_agent_id(tenant: str) -> str:
    """Extract agent ID from a tenant string.
    
    Args:
        tenant: Tenant string ("master" or "agent:<agent_id>").
    
    Returns:
        str: Agent ID, or None if tenant is "master".
    """
    if tenant == TENANT_MASTER:
        return None
    if tenant.startswith(TENANT_AGENT_PREFIX):
        return tenant[len(TENANT_AGENT_PREFIX):]
    return None


def is_master_tenant(tenant: str) -> bool:
    """Check if tenant is the master tenant.
    
    Args:
        tenant: Tenant string.
    
    Returns:
        bool: True if master tenant.
    """
    return tenant == TENANT_MASTER


def is_agent_tenant(tenant: str) -> bool:
    """Check if tenant is an agent tenant.
    
    Args:
        tenant: Tenant string.
    
    Returns:
        bool: True if agent tenant.
    """
    return tenant.startswith(TENANT_AGENT_PREFIX)
