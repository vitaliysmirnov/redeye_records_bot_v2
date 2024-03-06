#!/usr/bin/env python
#
# -*- coding: utf-8 -*-

import sqlite3
import logging
from time import sleep
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from config import API_HOST, DB_PATH, REDEYE_URL, REDEYE_CDN, selections, tables


class Parser:
    """Parser is independent app module. Can be hosted anywhere"""
    def __init__(self):
        self.headers = {
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
                          " Chrome/73.0.3683.103 Safari/537.36"
        }

    @staticmethod
    def generate_tables_and_urls(selection):
        """Get tables and redeyerecords urls related with selection. Returns dict() object"""
        selection_for_url = selection.replace("_", "-")
        tables_and_urls = {
            f"{selection}_preorders": f"{REDEYE_URL}/{selection_for_url}/pre-orders",
            f"{selection}_new": f"{REDEYE_URL}/{selection_for_url}/new-releases",
            f"{selection}_discount30": f"{REDEYE_URL}/{selection_for_url}/sale-section",
            f"{selection}_discount50": f"{REDEYE_URL}/{selection_for_url}/super-sale-section",
            f"{selection}_discount75": f"{REDEYE_URL}/{selection_for_url}/super-super-sale-section"
        }
        return tables_and_urls

    def get_data_from_url(self, url):
        """Get data from redeyerecords"""
        session = requests.Session()
        logging.info(f"Trying to get {url}")
        request = session.get(url, headers=self.headers)
        if request.status_code == 200:
            logging.debug(f"{url} status code: {request.status_code}")
            soup = BeautifulSoup(request.content, "html.parser")
            releases = soup.findAll("div", attrs={"class": "releaseGrid"})
            logging.info(f"{len(releases)} releases found at {url}")
            return releases[::-1]
        else:
            logging.warning(f"{url} status code: {request.status_code}. Try again in 300 seconds.")
            sleep(300)
            self.get_data_from_url(url)

    def set_db_tables(self):
        """Create tables in database"""
        db_connection = sqlite3.connect(DB_PATH)
        db_cursor = db_connection.cursor()

        for selection in selections.keys():
            tables_and_urls = self.generate_tables_and_urls(selection)
            for table in tables_and_urls.keys():
                db_cursor.execute(
                    f"""
                        DROP TABLE IF EXISTS {table}
                    """
                )
                logging.info(f"Table {table} deleted")
                db_connection.commit()
                db_cursor.execute(
                    f"""
                        CREATE TABLE {table} (
                            item_id INT,
                            redeye_id INT,
                            item VARCHAR,
                            samples VARCHAR,
                            img VARCHAR,
                            selection VARCHAR,
                            registered_at TIMESTAMP
                    );
                    """
                )
                db_connection.commit()
                logging.info(f"New table {table} created")

        db_connection.close()

    @staticmethod
    def combine_release_data(release, selection, section):
        """Combine releases data from web for usage"""
        redeye_id = release["id"]
        title = release.find("p", attrs={"class": "artist"}).text
        label = release.find("p", attrs={"class": "label"})
        label = f"{label.contents[2].text} – {label.contents[0]}"
        tracklist = release.find("p", attrs={"class": "tracks"}).text
        samples = release.findAll("a", attrs={"class": "btn-play"})
        samples_str = ""
        if len(samples) > 0:
            samples_str = f"{REDEYE_CDN}/{redeye_id}.mp3"
            samples_str += "".join(
                [f",{REDEYE_CDN}/{redeye_id}{chr(i + 97)}.mp3" for i in range(1, len(samples))])
        samples = samples_str
        price = release.find("div", attrs={"class": "price"}).text.replace("!", "!\n")
        img = release.find("img")["src"]
        release_url = release.find("a")["href"]
        item = (f"*{selections[selection]}*\n"
                f"{section}\n\n"
                f"*{title}*\n"
                f"_{label}_\n\n"
                f"{tracklist}\n"
                f"{price}"
                f"{release_url}")

        return int(redeye_id), item, samples, img

    def db_initiation(self):
        """Method that fills database with actual releases data"""
        self.set_db_tables()

        db_connection = sqlite3.connect(DB_PATH)
        db_cursor = db_connection.cursor()

        for selection in selections.keys():
            tables_and_urls = self.generate_tables_and_urls(selection)
            for table, url in tables_and_urls.items():
                section = tables[table.split("_")[-1]]
                releases = self.get_data_from_url(url)
                for release in releases:
                    redeye_id, item, samples, img = self.combine_release_data(release, selection, section)
                    db_cursor.execute(
                        f"""
                            INSERT INTO {table} (item_id, redeye_id, item, samples, img, selection, registered_at)
                            VALUES ((SELECT count(item_id) FROM {table}) + 1, ?, ?, ?, ?, ?, ?)
                        ;
                        """, (redeye_id, item, samples, img, selection, str(datetime.now(timezone.utc)))
                    )
                    db_connection.commit()

        db_connection.close()

    def check_new_releases(self):
        """Method that checks redeyerecords for new releases"""
        db_connection = sqlite3.connect(DB_PATH)
        db_cursor = db_connection.cursor()

        for selection in selections.keys():
            tables_and_urls = self.generate_tables_and_urls(selection)
            for table, url in tables_and_urls.items():
                section = tables[table.split("_")[-1]]

                db_cursor.execute(f"SELECT redeye_id FROM {table}")
                db_redeye_ids = db_cursor.fetchall()
                logging.info(f"Redeye IDs in {table}: {db_redeye_ids}")

                releases = self.get_data_from_url(url)
                for release in releases:
                    redeye_id, item, samples, img = self.combine_release_data(release, selection, section)
                    if (redeye_id,) not in db_redeye_ids:
                        db_cursor.execute(
                            f"""
                                DELETE FROM {table} WHERE item_id = (SELECT MIN(item_id) FROM {table})
                            ;
                            """
                        )
                        db_connection.commit()
                        logging.info(f"The oldest release in {table} was deleted from DB to cleanup space")
                        db_cursor.execute(
                            f"""
                                INSERT INTO {table} (item_id, redeye_id, item, samples, img, selection, registered_at)
                                VALUES ((SELECT count(item_id) FROM {table}) + 1, ?, ?, ?, ?, ?, ?)
                            ;
                            """, (redeye_id, item, samples, img, selection, str(datetime.now(timezone.utc)))
                        )
                        db_connection.commit()
                        logging.info(f"New release added to DB. Redeye ID: {redeye_id}")

                        data = {
                            "redeye_id": redeye_id,
                            "table": table
                        }
                        request = requests.post(f"{API_HOST}/new_release", json=data)
                        if request.status_code != 200:
                            logging.warning(f"Can't reach API! Status code: {request.status_code}")

        db_connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename="redeye_records_parser.log", filemode="w", format="%(asctime)s %(levelname)s %(message)s")

    p = Parser()
    try:
        p.db_initiation()
        while True:
            sleep(600)
            p.check_new_releases()
    except Exception as e:
        logging.critical(e)
