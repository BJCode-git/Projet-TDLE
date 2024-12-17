
import json
from random import randint, choice, seed as random_seed, random
from faker import Faker
from datetime import datetime
from os import getenv
from dotenv import load_dotenv
from dataclasses import dataclass
from alive_progress import alive_bar

"""
Collection/Table "Books" :
	id : Identifiant unique (UUID ou Auto-increment pour MySQL, ObjectId pour MongoDB)
	title : Titre du livre (String)
	author : Auteur du livre (String)
	published_date : Date de publication (Date)
	genre : Genre du livre (String)
	price : Prix du livre (Float)
	copies_sold : Nombre d'exemplaires vendus (Integer)
	rand: Champ aléatoire pour les tests entre 0 et num_records_per_many-1 (Integer)
"""


# Générateur de données
faker = Faker("fr_FR")
faker.seed_instance(1234)

random_seed(1234)


# Configuration
num_records				= 10000
num_records_per_many	= 10
generated_file			= "generated-data/books.json"
updated_file			= "generated-data/updated_books.json"


# Genres de livres disponibles
genres = ["Fiction", "Non-Fiction", "Science", "Fantasy", "Biography", "Romance", "Thriller"]
@dataclass
class Book:
	id: str 					= 0
	title: str 					= ""
	author: str 				= ""
	published_date: datetime	= datetime.now()
	genre: str					= genres[0]
	price: float				= 1.0
	copies_sold: int			= 0
	ran: int					= 0
	
 
def get_configuration():
	"""
	Get the configuration of the database
	"""
	global num_records, num_records_per_many, generated_file, updated_file
	
	if get_configuration.loaded:
		return
 
	try:
		load_dotenv()
	except Exception as e:
		print("Error loading environment variables : ", e)

	# Nombre de livres à générer
	num_records				 = int(getenv("NUM_RECORDS", 10000))
	num_records_per_many	 = int(getenv("NUM_RECORDS_PER_MANY", 10))
	generated_file			 = getenv("GENERATED_FILE_PATH", "generated-data/books.json")
	updated_file			 = getenv("UPDATED_FILE_PATH", "generated-data/updated_books.json")
	get_configuration.loaded = True
get_configuration.loaded = False


def generate_book(id=-1) -> dict:
	global faker, genres,num_records_per_many
	if id == -1:
		generate_book.id += 1
		id = generate_book.id
	
	return {
		"id":				id,
		"title":			faker.sentence(nb_words=randint(1, 6)),
		"author":			faker.name(),
		"published_date":	faker.date_between(start_date="-250y", end_date="today").strftime("%Y-%m-%d"),
		"genre":			choice(genres),
		"price":			random() *50  + 5,
		"copies_sold":		randint(0, 1000000),
		"ran":				randint(0, num_records_per_many-1)
	}
generate_book.id = -1
 
def generate_dataset(num_records):
 
	books = []
	# Générer les données
	with alive_bar(num_records) as bar: 
		bar.text("Generating data...")
		for i in range(num_records):
			books.append(generate_book(i))
			bar()
	
	return books

def extract_books_from_file(file, max_data:int = num_records) -> list[dict]:
	"""
		Extract the books from file to a list of Books
		__param file: str
		__return: list of books
	"""
	with open(file, "r") as f:
		data = json.load(f)
		books = []
  
		i = 0
		for item in data:
			books.append(Book(	id=item["id"], 
								title=item["title"], 
								author=item["author"], 
								published_date=item["published_date"], 
								genre=item["genre"], 
								copies_sold=item["copies_sold"],
								price=item["price"],
								ran=item["ran"]
							).__dict__
						)
			i+=1
			if i >= max_data:
				break

	return books	

def extract_updated_books_from_file(file, max_data:int = num_records):
	with open(file, "r") as f:
		data = json.load(f)
		books = []
  
		i = 0
		for item in data:
			original = item["original"]
			modified = item["modified"]
			original_book = Book(	id=original["id"],
									title=original["title"],
									author=original["author"],
									published_date=original["published_date"],
									genre=original["genre"],
									copies_sold=original["copies_sold"],
									price=original["price"],
									ran=original["ran"]).__dict__
			modified_book = Book(	id=modified["id"],
									title=modified["title"],
									author=modified["author"],
									published_date=modified["published_date"],
									genre=modified["genre"],
									copies_sold=modified["copies_sold"],
									price=modified["price"],
									ran=modified["ran"]).__dict__
			books.append((original_book, modified_book))

			i+=1
			if i >= max_data:
				break

	return books

def modify_book(book):
	global  genres
	update_faker = Faker("fr_FR")
	update_faker.seed_instance(9876)
 
	# On modifie un champ aléatoire
	
	new_book = book.copy()
	tries = 0
	max_tries = 10
	match randint(1, 6):

		case 1:
			while new_book["title"] == book["title"] or tries < max_tries:
				tries += 1
				new_book["title"] = update_faker.sentence(nb_words=randint(1, 6))
		case 2:
			while new_book["author"] == book["author"] or tries < max_tries:
				tries += 1
				new_book["author"] = update_faker.name()
		case 3:
			while new_book["published_date"] == book["published_date"] or tries < max_tries:
				tries += 1
				new_book["published_date"] = update_faker.date_between(start_date="-250y", end_date="today").strftime("%Y-%m-%d")
		case 4:
			while new_book["genre"] == book["genre"] or tries < max_tries:
				tries += 1
				new_book["genre"] = choice(genres)
		case 5:
			while new_book["price"] == book["price"] or tries < max_tries:
				tries += 1
				new_book["price"] = random() * 50 + 5
		case 6:
			while new_book["copies_sold"] == book["copies_sold"] or tries < max_tries:
				tries += 1
				new_book["copies_sold"] = randint(0, 1000000)
		case _:
			# Par défaut, on modifie le prix
			new_book["price"] = new_book["price"] + 1

	return new_book

def update_dataset(dataset):
	"""
		update dataset in place
		__param dataset: list of dictionaries
	"""

	with alive_bar(num_records) as bar:
		bar.text("Generating updates values..")
		for i in range(0,len(dataset)):
			original	= dataset[i]
			modified	= modify_book(original)
			dataset[i]	= {"original": original, "modified": modified}
			bar()


def save_to_file(data, filename):
	with open(filename, "w",encoding='utf8') as f:
		json.dump(data, f,indent=4, ensure_ascii=False)


if __name__ == "__main__":
	# Récupérer la configuration
	get_configuration()

	# Générer les données
	dataset=generate_dataset(num_records)
 
	# Enregistrer les données dans un fichier
	save_to_file(dataset, generated_file)

	# Génération des données à modifier
	# On génère de nouvelles graines pour les données modifiées
	random_seed(9876)
	update_dataset(dataset)
 
	# Enregistrer les données dans un fichier
	save_to_file(dataset, updated_file)
	
	print("Data generated successfully")