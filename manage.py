from app import create_app
from app.extensions import db
from scripts.seed import seed_data

app = create_app()


@app.cli.command("seed")
def seed():
    seed_data(db.session)
    db.session.commit()
    print("Datos iniciales creados o actualizados.")
