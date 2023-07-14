import os
import io

def write_int_to_file(filename, number):
    with open(filename, "wb") as f:
        f.write(number.to_bytes((number.bit_length() + 7) // 8, 'big'))

def read_int_from_file(filename):
    with open(filename, "rb") as f:
        return int.from_bytes(f.read(), 'big')
        
def read_last_line(filename):
    with open(filename, 'rb') as f:
        if f.readline():  # Check file is not empty
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b'\n':
                f.seek(-2, io.SEEK_CUR)
            last_line = f.readline().decode()
        else:
            last_line = ''
    return last_line

