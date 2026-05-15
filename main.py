from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

# In-memory database
items = []


# Request body model
class Item(BaseModel):
    id: int
    name: str
    price: float


# Home route
@app.get("/")
def home():
    return {"message": "FastAPI Demo App"}


# Get all items
@app.get("/items", response_model=List[Item])
def get_items():
    return items


# Add new item
@app.post("/items")
def add_item(item: Item):
    items.append(item)
    return {
        "message": "Item added successfully",
        "item": item
    }


# Get single item by ID
@app.get("/items/{item_id}")
def get_item(item_id: int):
    for item in items:
        if item.id == item_id:
            return item

    return {"error": "Item not found"}


# Delete item
@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    for item in items:
        if item.id == item_id:
            items.remove(item)
            return {"message": "Item deleted"}

    return {"error": "Item not found"}
