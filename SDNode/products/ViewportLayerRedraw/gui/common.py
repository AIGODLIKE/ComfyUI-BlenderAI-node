def hex2rgb(hex_val: str):
    hex_val = hex_val.lstrip("#")
    r, g, b = tuple(int(hex_val[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return r, g, b


def hex2rgba(hex_val: str):
    # 去除 # 并转为小写
    hex_val = hex_val.lstrip('#').lower()
    length = len(hex_val)
    if length not in (3, 4, 6, 8):
        raise ValueError(f"Invalid HEX length: {length}")

    # 处理简写格式
    if length == 3:
        hex_val = ''.join([c * 2 for c in hex_val]) + 'ff'  # RRGGBB + FF
    elif length == 4:
        hex_val = ''.join([c * 2 for c in hex_val])          # RRGGBBAA
    elif length == 6:
        hex_val += 'ff'                                      # RRGGBB + FF

    # 确保处理后的长度为8
    if len(hex_val) != 8:
        raise ValueError("Failed to expand HEX to 8 characters")

    # 解析为整数
    r, g, b, a = tuple(int(hex_val[i:i + 2], 16) / 255 for i in (0, 2, 4, 6))
    return r, g, b, a
