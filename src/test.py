import replicate
from dotenv import load_dotenv

load_dotenv()
print(replicate.paginate(replicate.collections.list))
collections = [
    collection
    for page in replicate.paginate(replicate.collections.list)
    for collection in page
]

print(replicate.collections.get("flux-fine-tunes").models)
