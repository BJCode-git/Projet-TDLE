
import json
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
	ran: Champ aléatoire pour les tests entre 0 et num_records_per_many-1 (Integer)
"""


# Générateur de données
faker 			= Faker("fr_FR")
update_faker	= Faker("fr_FR")



# Configuration
num_records				= 10000
num_records_per_many	= 10
nb_measurements			= 100
generated_file			= "generated-data/books.json"
updated_file			= "generated-data/updated_books.json"
seed_generation			= 1234
seed_update				= 9876


# Genres de livres disponibles
genres = ["Fiction", "Non-Fiction", "Science", "Fantasy", "Biography", "Romance", "Thriller"]
@dataclass
class Book:
	id: int 					= 0
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
	global num_records, num_records_per_many, nb_measurements
	global generated_file, updated_file
	global faker,update_faker 
	global seed_generation, seed_update
 
	if get_configuration.loaded:
		return
 
	try:
		load_dotenv()
	except Exception as e:
		print("Error loading environment variables : ", e)

	# Nombre de livres à générer
	num_records				 = int(getenv("NUM_RECORDS", 10000))
	num_records_per_many	 = int(getenv("NUM_RECORDS_PER_MANY", 10))
	nb_measurements			 = int(getenv("NB_MEASUREMENTS", 100))
	generated_file			 = getenv("GENERATED_FILE_PATH", "generated-data/books.json")
	updated_file			 = getenv("UPDATED_FILE_PATH", "generated-data/updated_books.json")
 
	seed_generation			 = int(getenv("SEED_GENARATION", 1234))
	seed_update				 = int(getenv("SEED_UPDATE", 9876))
	
	# On fixe les graines pour les données générées
	faker.seed_instance(seed_generation)
	update_faker.seed_instance(seed_update)
 
	get_configuration.loaded = True	
get_configuration.loaded = False
# Récupérer la configuration
get_configuration()

def format_book_dict(book:dict) -> Book:
	"""
		Convert a dictionary to a Book object
		__param book: dict
		__return: Book
	"""
	
	book["id"] = int(book["id"])
	book["published_date"] = datetime.strptime(book["published_date"], "%Y-%m-%d")
	book["price"] = float(book["price"])
	book["copies_sold"] = int(book["copies_sold"])


def generate_book(id=-1) -> dict:
	global faker, genres,num_records_per_many
	if id == -1:
		generate_book.id += 1
		id = generate_book.id

	b 					= Book()
	b.id 				= id
	b.title				= faker.sentence(nb_words=faker.random_int(1, 6))
	b.author			= faker.name()
	# Date de publication entre -250 ans et aujourd'hui au format MYSQL (YYYY-MM-DD)
	b.published_date	= faker.date_between(start_date="-250y", end_date="today").strftime("%Y-%m-%d")
	b.genre				= genres[faker.random_int(0, len(genres)-1)]
	# Prix entre 5 et 100 euros + centimes
	b.price				= faker.random_int(5,99) + faker.random_int(0,100)/100
	b.copies_sold		= faker.random_int(0, 1000000)
	b.ran				= faker.random_int(0, num_records_per_many-1)

	return b.__dict__ 
generate_book.id = -1

def generate_dataset(num_records) -> list[dict]:
	"""
		Générer un ensemble de données
		__param num_records: int
		__return: list of books
	"""
 
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
			
			format_book_dict(item)
			books.append(item)

			i+=1
			if i >= max_data:
				break

	return books

def extract_updated_books_from_file(file, max_data:int = num_records) -> list[dict]:
	with open(file, "r") as f:
		data = json.load(f)
		books = []
  
		i = 0
		for item in data:
			original = item["original"]
			modified = item["modified"]

			format_book_dict(original)
			format_book_dict(modified)

			books.append((original, modified))

			i+=1
			if i >= max_data:
				break

	return books

def modify_book(book:dict) -> dict:
	global  genres
	
	# On modifie un champ aléatoire
	new_book = book.copy()
	tries = 0
	max_tries = 10
	match update_faker.random_int(1, 6):

		case 1:
			while new_book["title"] == book["title"] or tries < max_tries:
				tries += 1
				new_book["title"] = update_faker.sentence(nb_words=update_faker.random_int(1, 6))
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
				new_book["genre"] =  genres[update_faker.random_int(0, len(genres)-1)]
		case 5:
			while new_book["price"] == book["price"] or tries < max_tries:
				tries += 1
				new_book["price"] = update_faker.random_int(5,99) + update_faker.random_int(0,100)/100 
		case 6:
			while new_book["copies_sold"] == book["copies_sold"] or tries < max_tries:
				tries += 1
				new_book["copies_sold"] = update_faker.random_int(0, 1000000)
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

	# Générer les données
	dataset=generate_dataset(num_records)
 
	# Enregistrer les données dans un fichier
	save_to_file(dataset, generated_file)

	# Génération des données à modifier
	# On génère de nouvelles graines pour les données modifiées
	update_dataset(dataset)
 
	# Enregistrer les données dans un fichier
	save_to_file(dataset, updated_file)
	
	print("Data generated successfully")