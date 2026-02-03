import os

def load_from_config(setting_name: str, default_value:str=None) -> str | None:
    """
    Searches a setting name and return its value from the setting.cfg file

    :param setting_name: setting name in the setting.cfg file
    :type setting_name: str
    :return: the setting value, or None if not found
    :rtype: str | None
    """
    config_path = os.path.join(os.path.dirname(__file__), "settings.cfg")

    with open(config_path, "r") as f:
        for line in f:
            line = line.split("#")[0].strip()  # Remove comments
            if not line:
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == setting_name:
                    value = value.strip().strip('"').strip("'")
                    return value
    return default_value




def time_string_to_int(time_string: str) -> list[int]:
    """
    Converts time in the string form "HH:MM" 24h to [HH, MM] int array

    :param time_string: time in "HH:MM" 24h string format
    :type time_string: str
    :return: [hours, minutes] as integers, or empty list if invalid
    :rtype: list[int]
    """
    try:
        parts = time_string.split(":")
        if len(parts) != 2:
            return []
        hours, minutes = int(parts[0]), int(parts[1])
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return [hours, minutes]
    except ValueError:
        pass
    return []