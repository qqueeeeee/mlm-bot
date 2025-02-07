from src.models.db import Base, engine

# Create tables in the database
print("Initializing database...")
Base.metadata.create_all(engine)
print("Database initialized successfully.")