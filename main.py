import os
import csv
import logging
import pandas as pd
import matplotlib.pyplot as plt

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from datetime import datetime, timedelta

LOG = logging.getLogger(__name__)
logging.basicConfig(
    filename="database_logs.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s::%(funcName)s: %(message)s"
)

YEARS = [2019, 2020]


def get_previous_run_time(last_row_coll: Collection):
    previous_run_work_time = last_row_coll.find_one()["previous_work_time"]
    return timedelta(microseconds=previous_run_work_time)


def get_user_query(test_coll: Collection, filename):
    """Варіант 14: Порівняти середній бал з Англійської мови у кожному регіоні у 2020 та 2019 роках
    серед тих кому було зараховано тест"""
    LOG.info("Getting data for users query")
    user_query = test_coll.aggregate(
        [
            {"$match": {"engTestStatus": "Зараховано"}},
            {"$group": {"_id": {"year": "$TestYear",
                                "region": "$REGNAME"},
                        "engAverageMark": {"$avg": "$engBall100"}}},
        ]
    )

    with open(filename, "w") as csvfile:
        csq_writer = csv.DictWriter(csvfile, fieldnames=["year", "region", "engAverageMark"])
        csq_writer.writeheader()
        for row in user_query:
            row["year"] = row["_id"]["year"]
            row["region"] = row["_id"]["region"]
            del row["_id"]
            print(row)
            csq_writer.writerow(row)
    LOG.info(f"Users query data recorded into {filename}")


def build_plot(filename):
    LOG.info(f"Building plot for data from {filename} file")
    data = pd.read_csv(filename, sep=',')
    data['year_region'] = data['year'].astype(str) + "-" + data['region']

    figure = data.plot.bar(x='year_region', y='engAverageMark', color="orange", figsize=(20, 7))
    plt.ylabel('Середній бал')
    plt.xlabel('рік-регіон')
    plt.title(
        'Середній бал з Англійської мови у кожному регіоні у 2020 та 2019 роках серед тих, кому було зараховано тест'
    )
    for p in figure.patches:
        figure.annotate(str(p.get_height()), (p.get_x() * 1.0001, p.get_height() * 0.02), rotation=90)

    picture_path = 'results_photo/AverageMarkByRegion.png'
    plt.savefig(picture_path, bbox_inches='tight')
    LOG.info(f"Plot saved into {picture_path}")


def create_last_row_collection(db: Database):
    LOG.info("Creating collections")
    collections = db.list_collection_names()
    if "last_row" not in collections:
        last_row_coll = db["last_row"]
        last_row_coll.insert_one({"year": YEARS[0],
                                  "previous_work_time": 0,
                                  "row_number": 0})
    return 0


def insert_data_into_collections(iteration, test_coll: Collection, last_row_coll: Collection,
                                 dicts_to_write, now, previous_stack_time, start_time):
    try:
        if(dicts_to_write):
            test_coll.insert_many(dicts_to_write)
            last_row_coll.update_one({}, {"$set": {"row_number": iteration},
                                          "$inc": {"previous_work_time": (now - previous_stack_time).microseconds}})
    except Exception as e:
        end_time = datetime.now()
        LOG.info(f"Break time {end_time}")
        LOG.info(f"Executing time {end_time - start_time}")
        LOG.info(f"Я упал: {e}")
        raise e
    return 0


def clean_dict(dict_to_clean, year):
    dict_to_clean["TestYear"] = year
    for key in dict_to_clean:
        try:
            new_value = float(dict_to_clean[key].replace(",", "."))
            dict_to_clean[key] = new_value
        except Exception:
            pass
    return dict_to_clean


def insert_data(test_coll: Collection, last_row_coll: Collection, csv_filename, year, last_row_number, start_time):
    previous_stack_time = start_time
    LOG.info(f"Inserting data from {last_row_number} row from file for {year} year")

    with open(csv_filename, encoding="cp1251") as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=';')

        i = 0
        dicts_to_write = []
        last_row_coll.update_one({}, {"$set": {"year": year}})
        for row in csv_reader:
            i += 1
            print(i)
            if i <= last_row_number:
                continue

            formatted_dict = clean_dict(row, year)
            dicts_to_write.append(formatted_dict)

            if i % 50 == 0:
                now = datetime.now()
                insert_data_into_collections(i, test_coll, last_row_coll, dicts_to_write,
                                             now, previous_stack_time, start_time)
                dicts_to_write = []
                previous_stack_time = now

    if i % 50 != 0:
        now = datetime.now()
        insert_data_into_collections(i, test_coll, last_row_coll, dicts_to_write,
                                     now, previous_stack_time, start_time)

    LOG.info(f"Inserting from {csv_filename} is finished")


def main():
    start_time = datetime.now()
    LOG.info(f"Start time {start_time}")

    client = MongoClient(port=int(os.environ.get("mongodb_port")))
    db = client.db_lab4

    create_last_row_collection(db)
    test_coll, last_row_coll = db.test, db.last_row
    print(test_coll, last_row_coll)
    last_row_coll_values = last_row_coll.find_one()
    year, row_number = last_row_coll_values["year"], last_row_coll_values["row_number"]

    index = YEARS.index(year)
    for year in YEARS[index:]:
        insert_data(test_coll, last_row_coll, f"Odata{year}File.csv", year, row_number, start_time)
        row_number = 0

    inserting_time = get_previous_run_time(last_row_coll)
    end_time = datetime.now()
    LOG.info(f"End time {end_time}")
    LOG.info(f"Inserting executing time {end_time - start_time}")

    filename = "resultFile.csv"

    get_user_query(test_coll, filename)

    build_plot(filename)

    client.close()

    LOG.info("Program is finished")
    LOG.info(f"Total inserting executing time {inserting_time}")


if __name__ == "__main__":
    main()

#  number of all rows in files = 733112
