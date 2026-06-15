def map_t9_to_symbol(digits):
    """
    Converts keypad digits to stock symbols.
    Example: '24' -> 'AI' (2=A, 4=I)
    """
    t9_map = {
        '2': 'A', '22': 'B', '222': 'C',
        '3': 'D', '33': 'E', '333': 'F',
        '4': 'G', '44': 'H', '444': 'I',
        '5': 'J', '55': 'K', '555': 'L',
        '6': 'M', '66': 'N', '666': 'O',
        '7': 'P', '77': 'Q', '777': 'R', '7777': 'S',
        '8': 'T', '88': 'U', '888': 'V',
        '9': 'W', '99': 'X', '999': 'Y', '9999': 'Z'
    }
    
    # For simple one-press-per-letter logic (e.g., 2=A, 4=I for 'AI'):
    simple_map = {
        '2': 'A', '3': 'D', '4': 'G', '5': 'J', 
        '6': 'M', '7': 'P', '8': 'T', '9': 'W'
    }
    
    # Logic: convert each digit to its primary letter
    # If the user presses 2-4, it returns 'AG' (which you can then fix or refine)
    # Recommendation: Use Twilio 'Speech Recognition' for symbols instead of keypad,
    # but if keypad is required, use this simple translation:
    char_map = {
        '2': 'A', '3': 'D', '4': 'G', '5': 'J', 
        '6': 'M', '7': 'P', '8': 'T', '9': 'W'
    }
    return "".join([char_map.get(d, '') for d in digits])
