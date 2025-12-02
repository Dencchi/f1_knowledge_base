from django import template

register = template.Library()

COUNTRY_CODES = {
    'Australia': 'au', 'Austria': 'at', 'Azerbaijan': 'az', 'Bahrain': 'bh',
    'Belgium': 'be', 'Brazil': 'br', 'Canada': 'ca', 'China': 'cn',
    'France': 'fr', 'Germany': 'de', 'Hungary': 'hu', 'Italy': 'it',
    'Japan': 'jp', 'Mexico': 'mx', 'Monaco': 'mc', 'Netherlands': 'nl',
    'Portugal': 'pt', 'Qatar': 'qa', 'Russia': 'ru', 'Saudi Arabia': 'sa',
    'Singapore': 'sg', 'Spain': 'es', 'Turkey': 'tr', 'UAE': 'ae', 'United States': 'us',
    'UK': 'gb', 'USA': 'us', 'United Kingdom': 'gb', 'Korea': 'kr', 'India': 'in'
}

@register.filter
def get_flag_code(country_name):
    return COUNTRY_CODES.get(country_name, 'xx').lower()