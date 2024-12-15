
import json
from random import randint, choice, seed as random_seed
from faker import Faker
from datetime import datetime
from os import getenv
from dotenv import load_dotenv
from dataclasses import dataclass

"""
Collection/Table "Books" :
	id : Identifiant unique (UUID ou Auto-increment pour MySQL, ObjectId pour MongoDB)
	title : Titre du livre (String)
	author : Auteur du livre (String)
	published_date : Date de publication (Date)
	genre : Genre du livre (String)
	copies_sold : Nombre d'exemplaires vendus (Integer)
"""


# Générateur de données
faker = Faker("fr_FR")
Faker.seed(1234)
random_seed(1234)


# Configuration
num_records				= 10000
num_records_per_many	= 10
generated_file			= "books.json"
updated_file			= "updated_books.json"


# Genres de livres disponibles
genres = ["Fiction", "Non-Fiction", "Science", "Fantasy", "Biography", "Romance", "Thriller"]
@dataclass
class Book:
	id: str 					= 0
	title: str 					= ""
	author: str 				= ""
	published_date: datetime	= datetime.now()
	genre: str					= genres[0]
	copies_sold: int			= 0

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

# Récupérer la configuration
get_configuration()

def generate_book():
	global faker, genres
	generate_book.id += 1
	return {
		"id":				generate_book.id,
		"title":			faker.sentence(nb_words=randint(1, 6)),
		"author":			faker.name(),
		"published_date":	faker.date_between(start_date="-250y", end_date="today").strftime("%Y-%m-%d"),
		"genre":			choice(genres),
		"copies_sold":		randint(0, 1000000)
	}
generate_book.id = -1
 
def generate_dataset(num_records):
	return [generate_book() for _ in range(num_records)]

def extract_books_from_file(file):
	"""
		Extract the books from file to a list of Books
		__param file: str
		__return: list of books
	"""
	with open(file, "r") as f:
		data = json.load(f)
		books = []
		for item in data:
			books.append(Book(	id=item["id"], 
								title=item["title"], 
								author=item["author"], 
								published_date=item["published_date"], 
								genre=item["genre"], 
								copies_sold=item["copies_sold"]))

	return books	

def extract_updated_books_from_file(file):
	with open(file, "r") as f:
		data = json.load(f)
		books = []
		for item in data:
			original = item["original"]
			modified = item["modified"]
			original_book = Book(	id=original["id"],
									title=original["title"],
									author=original["author"],
									published_date=original["published_date"],
									genre=original["genre"],
									copies_sold=original["copies_sold"])
			modified_book = Book(	id=modified["id"],
									title=modified["title"],
									author=modified["author"],
									published_date=modified["published_date"],
									genre=modified["genre"],
									copies_sold=modified["copies_sold"])
			books.append((original_book, modified_book))

	return books

def modify_book(book):
	global faker, genres
 
	# On modifie un champ aléatoire
	match randint(1, 5):
		case 1:
			book["title"] = faker.sentence(nb_words=randint(1, 6))
		case 2:
			book["author"] = faker.name()
		case 3:
			book["published_date"] = faker.date_between(start_date="-250y", end_date="today").strftime("%Y-%m-%d")
		case 4:
			book["genre"] = choice(genres)
		case 5:
			book["copies_sold"] = randint(0, 1000000)

	return book

def update_dataset(dataset):
	"""
		update dataset in place
		__param dataset: list of dictionaries
	"""
	for i in range(0,len(dataset)):
		original	= dataset[i]
		modified	= modify_book(original)
		dataset[i]	= {"original": original, "modified": modified}


def save_to_file(data, filename):
	with open(filename, "w",encoding='utf8') as f:
		json.dump(data, f,indent=4, ensure_ascii=False)

if __name__ == "__main__":
	
	# Générer les données
	dataset = generate_dataset(num_records)
	# Enregistrer les données dans un fichier
	save_to_file(dataset, generated_file)
	
	# Génération des données à modifier
	update_dataset(dataset)
	# Enregistrer les données dans un fichier
	save_to_file(dataset, updated_file)
	
	print("Data generated successfully")