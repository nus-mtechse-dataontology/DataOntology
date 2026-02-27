import hashlib
from datetime import datetime
import uuid

data = f"27wupj4xvbsgv4nzkxdcbgud7z6qzncpkcg9m9reaxdq6a3rQAtvzBb2gf{str(int(datetime.now().timestamp()))}"
# Encode the string to bytes using .encode()
encoded_data = data.encode('utf-8')

# Create a SHA256 hash object and update it with the data
hash_object = hashlib.sha256(encoded_data)

print(hash_object.hexdigest())
print(str(uuid.uuid4()))