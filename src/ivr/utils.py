def map_t9_to_symbol(digits):
    """
    Translates digit pairs into letters.
    Logic: 21=A, 22=B, 23=C, 31=D, 32=E, 33=F, etc.
    Example: '2143' -> 'AI'
    """
    # Define the mapping for pairs
    pair_map = {
        '21': 'A', '22': 'B', '23': 'C',
        '31': 'D', '32': 'E', '33': 'F',
        '41': 'G', '42': 'H', '43': 'I',
        '51': 'J', '52': 'K', '53': 'L',
        '61': 'M', '62': 'N', '63': 'O',
        '71': 'P', '72': 'Q', '73': 'R', '74': 'S',
        '81': 'T', '82': 'U', '83': 'V',
        '91': 'W', '92': 'X', '93': 'Y', '94': 'Z'
    }
    
    symbol = ""
    # Loop through the digits in steps of 2
    for i in range(0, len(digits), 2):
        pair = digits[i:i+2]
        if pair in pair_map:
            symbol += pair_map[pair]
            
    return symbol.upper()
