"""Price service for applying agent markups.

This module handles price calculations including agent-specific markups.
"""

import logging
from decimal import Decimal
from models.constants import MARKUP_TYPE_FIXED, MARKUP_TYPE_PERCENT


def apply_markup(base_price: float, agent: dict = None) -> float:
    """Apply price markup based on agent configuration.
    
    Args:
        base_price: The base price of the item.
        agent: Agent document from database (optional, if None returns base price).
    
    Returns:
        float: The final price after applying markup.
    """
    if agent is None:
        return base_price
    
    pricing = agent.get('pricing', {})
    markup_type = pricing.get('markup_type', MARKUP_TYPE_PERCENT)
    markup_value = pricing.get('markup_value', 0)
    
    try:
        base = Decimal(str(base_price))
        markup = Decimal(str(markup_value))
        
        if markup_type == MARKUP_TYPE_FIXED:
            # Fixed amount markup
            final_price = base + markup
        elif markup_type == MARKUP_TYPE_PERCENT:
            # Percentage markup
            final_price = base * (Decimal('1') + markup / Decimal('100'))
        else:
            logging.warning(f"Unknown markup type: {markup_type}, using base price")
            final_price = base
        
        # Round to 2 decimal places
        final_price = final_price.quantize(Decimal('0.01'))
        return float(final_price)
        
    except Exception as e:
        logging.error(f"Error applying markup: {e}, using base price")
        return base_price


def calculate_markup_amount(base_price: float, agent_price: float) -> float:
    """Calculate the markup amount.
    
    Args:
        base_price: The base price.
        agent_price: The final agent price.
    
    Returns:
        float: The markup amount (agent_price - base_price).
    """
    try:
        base = Decimal(str(base_price))
        agent = Decimal(str(agent_price))
        markup = agent - base
        return float(markup.quantize(Decimal('0.01')))
    except Exception as e:
        logging.error(f"Error calculating markup amount: {e}")
        return 0.0
