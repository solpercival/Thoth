def format_ezaango_shift_data(dict_data:dict, custom_message:str="") -> str:
    """
    Formats the shift data from the ezaango shift getter into an email readable format
    
    :param dict_data: The ezaango shift information dict
    :type dict_data: dict
    :param custom_message: Custom message to be displayed on top of the shift details
    :type custom_message: str
    :return: Returns the email readable format
    :rtype: str
    """
    # Message first
    if custom_message == "":
        custom_message = dict_data["reasoning"]

    output:str = custom_message + "\n"

    # Then the shift data
    # Staff info
    staff_info:str = \
    f"""
    STAFF:
        · Name: {dict_data["staff"]["name"]}
        · ID: {dict_data["staff"]["id"]}
        · Email: {dict_data["staff"]["email"]}

    """

    # Shift information
    shift_info:str = "SHIFT(S):\n"

    for shift in dict_data["shifts"]:
        shift_info_add = \
        f"""        · {shift["client"]} at {shift["time"]} {shift["date"]}\n"""
        shift_info += shift_info_add

    # Additional information at the end
    add_info:str = "\n\nThis is an auto-generated email. Please do not reply."

    return output + staff_info + shift_info + add_info




