import json
import os

def create_lkn_index():
    """
    Creates an index for the LKAAT_Leistungskatalog.json file.
    The index maps LKNs to their byte offset in the file.
    """
    index = {}
    with open(os.path.join('data', 'LKAAT_Leistungskatalog.json'), 'rb') as f:
        # Find the start of the list
        while f.read(1) != b'[':
            pass

        # Read the list of objects
        while True:
            char = f.read(1)
            if char == b']':
                break
            if char == b'{':
                offset = f.tell() - 1
                obj_str = b'{'
                balance = 1
                while balance > 0:
                    char = f.read(1)
                    obj_str += char
                    if char == b'{':
                        balance += 1
                    elif char == b'}':
                        balance -= 1

                try:
                    obj = json.loads(obj_str)
                    lkn = obj.get('LKN')
                    if lkn:
                        index[lkn] = offset
                except json.JSONDecodeError:
                    # This can happen if there are extra commas at the end of the list
                    pass

    with open(os.path.join('data', 'lkn_index.json'), 'w') as f:
        json.dump(index, f)

if __name__ == '__main__':
    create_lkn_index()
