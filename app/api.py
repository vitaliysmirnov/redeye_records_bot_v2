#!/usr/bin/env python
#
# -*- coding: utf-8 -*-

from datetime import datetime, timezone

import telebot
import sqlite3
from telebot.apihelper import ApiException
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import request, jsonify, Blueprint
from flask_restx import Api, Resource, fields

from app.config import BOT_TOKEN, DB_PATH, ADMIN_CHAT_ID, selections


bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
blueprint = Blueprint("api", __name__, url_prefix="/api")
api = Api(app=blueprint, version="1", title="Redeye Records Bot API")
api = api.namespace("v1")
responses = {
    200: "OK",
    201: "Created",
    204: "Updated",
    500: "Internal Server Error"
}


@api.route("/start")
class Start(Resource):
    @api.doc(
        responses={
            200: "OK",
            201: "Created",
            500: "Internal Server Error"
        },
        body=api.model(
            "Register new user",
            {
                "user_chat_id": fields.Integer(
                    description="User's Telegram chat ID",
                    required=True
                ),
                "username": fields.String(
                    description="User's username",
                    required=False
                ),
                "first_name": fields.String(
                    description="User's first name",
                    required=False
                ),
                "last_name": fields.String(
                    description="User's last name",
                    required=False
                )
            }
        )
    )
    def post(self):
        """Register new user"""
        try:
            user_chat_id = request.json["user_chat_id"]
            username = request.json["username"]
            first_name = request.json["first_name"]
            last_name = request.json["last_name"]
            db_connection = sqlite3.connect(DB_PATH)
            db_cursor = db_connection.cursor()
            db_cursor.execute(
                f"""
                    SELECT user_id FROM users WHERE user_chat_id = {user_chat_id}
                ;
                """
            )
            user_id = bool(db_cursor.fetchone())
            if not user_id:
                db_cursor.execute(
                    f"""
                        INSERT INTO users (user_id, user_chat_id, username, first_name, last_name, is_active, registered_at)
                        VALUES ((SELECT count(user_id) FROM users) + 1, ?, ?, ?, ?, true, ?)
                    ;
                    """, (user_chat_id, username, first_name, last_name, str(datetime.now(timezone.utc)))
                )
                db_connection.commit()
                db_cursor.execute(
                    f"""
                        INSERT INTO subscriptions VALUES
                        ((SELECT user_id FROM users WHERE user_chat_id = {user_chat_id}),
                        false, false, false, false, false, false, false, false, false)
                    ;
                    """
                )
                db_connection.commit()
                status_code = 201
                additional_info = ""
            else:
                db_cursor.execute(
                    f"""
                        UPDATE users
                        SET username = ?,
                            first_name = ?,
                            last_name = ?,
                            is_active = true
                        WHERE user_chat_id = {user_chat_id}
                    ;
                    """, (username, first_name, last_name)
                )
                db_connection.commit()
                db_cursor.execute(
                    f"""
                        UPDATE subscriptions
                        SET bass_music = false,
                            drum_and_bass = false,
                            experimental = false,
                            funk_hip_hop_soul = false,
                            house_disco = false,
                            reggae = false,
                            techno_electro = false,
                            balearic_and_downtempo = false,
                            alternative_indie_folk_punk = false
                        WHERE user_id = (SELECT user_id FROM users WHERE user_chat_id = ?)
                    ;
                    """, (user_chat_id,)
                )
                db_connection.commit()
                status_code = 200
                additional_info = f". User {user_chat_id} already exists. All subscriptions removed"
            db_connection.close()

            return responses[status_code] + additional_info, status_code

        except Exception as e:
            api.abort(500, e.__doc__, status=responses[500], status_сode=500)


@api.route("/subscribe")
class Subscribe(Resource):
    @api.doc(
        responses=responses,
        body=api.model(
            "Set up user's subscriptions",
            {
                "user_chat_id": fields.Integer(
                    description="User's Telegram chat ID",
                    required=True
                ),
                "selection": fields.String(
                    description="Selection to follow",
                    required=True
                )
            }
        )
    )
    def put(self):
        """Set up user's subscriptions"""
        try:
            user_chat_id = request.json["user_chat_id"]
            selection = request.json["selection"]
            db_connection = sqlite3.connect(DB_PATH)
            db_cursor = db_connection.cursor()
            db_cursor.execute(
                f"""
                    UPDATE subscriptions
                    SET {selection} = true
                    WHERE user_id = (SELECT user_id FROM users WHERE user_chat_id = ?)
                ;
                """, (user_chat_id,)
            )
            db_connection.commit()
            db_connection.close()

            return jsonify(
                {
                    "status": responses[200],
                    "status_code": 200,
                    "message": {
                        "result": f"Subscribed to {selections[selection]}"
                    }
                }
            )

        except Exception as e:
            api.abort(500, e.__doc__, status=responses[500], status_сode=500)


@api.route("/unsubscribe")
class Unsubscribe(Resource):
    @api.doc(
        responses=responses,
        body=api.model(
            "Unsubscribe from all threads",
            {
                "user_chat_id": fields.Integer(
                    description="User's Telegram chat ID",
                    required=True
                )
            }
        )
    )
    def put(self):
        """Unsubscribe from all threads"""
        try:
            user_chat_id = request.json["user_chat_id"]
            db_connection = sqlite3.connect(DB_PATH)
            db_cursor = db_connection.cursor()
            db_cursor.execute(
                f"""
                    UPDATE subscriptions
                    SET bass_music = false,
                        drum_and_bass = false,
                        experimental = false,
                        funk_hip_hop_soul = false,
                        house_disco = false,
                        reggae = false,
                        techno_electro = false,
                        balearic_and_downtempo = false,
                        alternative_indie_folk_punk = false
                    WHERE user_id = (SELECT user_id FROM users WHERE user_chat_id = ?)
                ;
                """, (user_chat_id,)
            )
            db_connection.commit()
            db_connection.close()

            return jsonify(
                {
                    "status": responses[200],
                    "status_code": 200,
                    "message": {
                        "result": "Subscriptions are deleted. You can renew your subscriptions at /selections"
                    }
                }
            )

        except Exception as e:
            api.abort(500, e.__doc__, status=responses[500], status_сode=500)


@api.route("/my_subscriptions")
class MySubscriptions(Resource):
    @api.doc(
        responses=responses,
        body=api.model(
            "User's subscriptions info",
            {
                "user_chat_id": fields.Integer(
                    description="User's Telegram chat ID",
                    required=True
                )
            }
        )
    )
    def get(self):
        """User's subscriptions info"""
        try:
            user_chat_id = request.args["user_chat_id"]
            db_connection = sqlite3.connect(DB_PATH)
            db_cursor = db_connection.cursor()
            db_cursor.execute(
                """
                    SELECT bass_music,
                           drum_and_bass,
                           experimental,
                           funk_hip_hop_soul,
                           house_disco,
                           reggae,
                           techno_electro,
                           balearic_and_downtempo,
                           alternative_indie_folk_punk
                    FROM subscriptions
                    WHERE user_id = (SELECT user_id FROM users WHERE user_chat_id = ?)
                ;
                """, (user_chat_id,)
            )
            subscriptions = db_cursor.fetchone()
            db_connection.close()

            selections_l = list(selections.keys())
            result_raw = dict()
            for i in range(len(selections_l)):
                result_raw[selections_l[i]] = subscriptions[i]
            result = dict()

            result["BASS MUSIC"] = result_raw.pop("bass_music")
            result["DRUM & BASS • JUNGLE"] = result_raw.pop("drum_and_bass")
            result["AMBIENT • EXPERIMENTAL • DRONE"] = result_raw.pop("experimental")
            result["HIP HOP • SOUL • JAZZ • FUNK"] = result_raw.pop("funk_hip_hop_soul")
            result["HOUSE • DISCO"] = result_raw.pop("house_disco")
            result["REGGAE"] = result_raw.pop("reggae")
            result["TECHNO • ELECTRO"] = result_raw.pop("techno_electro")
            result["BALEARIC • DOWNTEMPO"] = result_raw.pop("balearic_and_downtempo")
            result["ALTERNATIVE / INDIE / FOLK / PUNK"] = result_raw.pop("alternative_indie_folk_punk")

            return jsonify(
                {
                    "status": responses[200],
                    "status_code": 200,
                    "message": {
                        "result": result
                    }
                }
            )

        except Exception as e:
            api.abort(500, e.__doc__, status=responses[500], status_сode=500)


@api.route("/stats")
class Stats(Resource):
    @api.doc(
        responses=responses,
        body=api.model(
            "Users statistics (available only for admin)",
            {
                "admin_chat_id": fields.Integer(
                    description="Admin's Telegram chat ID",
                    required=True
                ),
                "telegram_api_token": fields.String(
                    description="Telegram Bot API Token",
                    required=True
                )
            }
        )
    )
    def post(self):
        """Users statistics (available only for admin)"""
        try:
            admin_chat_id = request.json["admin_chat_id"]
            telegram_api_token = request.json["telegram_api_token"]
            if admin_chat_id == ADMIN_CHAT_ID and telegram_api_token == BOT_TOKEN:
                db_connection = sqlite3.connect(DB_PATH)
                db_cursor = db_connection.cursor()
                db_cursor.execute(
                    """
                        SELECT t1.users_total, 
                               t2.users_active
                        FROM
                        (SELECT count(user_id) AS users_total FROM users) AS t1,
                        (SELECT count(is_active) AS users_active FROM users WHERE is_active = true) AS t2
                    ;
                    """
                )
                users = db_cursor.fetchall()[0]
                result_users = {
                    "users_total": users[0],
                    "users_active": users[1]
                }

                db_cursor.execute(
                    """
                        SELECT t1.bass_music_subs_active, 
                               t2.drum_and_bass_subs_active, 
                               t3.experimental_subs_active, 
                               t4.funk_hip_hop_soul_subs_active, 
                               t5.house_disco_subs_active, 
                               t6.reggae_subs_active,
                               t7.techno_electro_subs_active,
                               t8.balearic_and_downtempo_subs_active,
                               t9.alternative_indie_folk_punk_subs_active,
                               t10.bass_music_subs_total, 
                               t11.drum_and_bass_subs_total, 
                               t12.experimental_subs_total, 
                               t13.funk_hip_hop_soul_subs_total, 
                               t14.house_disco_subs_total, 
                               t15.reggae_subs_total, 
                               t16.techno_electro_subs_total, 
                               t17.balearic_and_downtempo_subs_total, 
                               t18.alternative_indie_folk_punk_subs_total
                        FROM
                        (SELECT count(u.user_id) AS bass_music_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND bass_music = true) AS t1,
                        (SELECT count(u.user_id) AS drum_and_bass_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND drum_and_bass = true) AS t2,
                        (SELECT count(u.user_id) AS experimental_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND experimental = true) AS t3,
                        (SELECT count(u.user_id) AS funk_hip_hop_soul_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND funk_hip_hop_soul = true) AS t4,
                        (SELECT count(u.user_id) AS house_disco_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND house_disco = true) AS t5,
                        (SELECT count(u.user_id) AS reggae_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND reggae = true) AS t6,
                        (SELECT count(u.user_id) AS techno_electro_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND techno_electro = true) AS t7,
                        (SELECT count(u.user_id) AS balearic_and_downtempo_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND balearic_and_downtempo = true) AS t8,
                        (SELECT count(u.user_id) AS alternative_indie_folk_punk_subs_active FROM users u JOIN subscriptions s on u.user_id = s.user_id 
                            WHERE u.is_active = true AND alternative_indie_folk_punk = true) AS t9,
                        (SELECT count(*) AS bass_music_subs_total FROM subscriptions WHERE bass_music = true) AS t10,
                        (SELECT count(*) AS drum_and_bass_subs_total FROM subscriptions WHERE drum_and_bass = true) AS t11,
                        (SELECT count(*) AS experimental_subs_total FROM subscriptions WHERE experimental = true) AS t12,
                        (SELECT count(*) AS funk_hip_hop_soul_subs_total FROM subscriptions WHERE funk_hip_hop_soul = true) AS t13,
                        (SELECT count(*) AS house_disco_subs_total FROM subscriptions WHERE house_disco = true) AS t14,
                        (SELECT count(*) AS reggae_subs_total FROM subscriptions WHERE reggae = true) AS t15,
                        (SELECT count(*) AS techno_electro_subs_total FROM subscriptions WHERE techno_electro = true) AS t16,
                        (SELECT count(*) AS balearic_and_downtempo_subs_total FROM subscriptions WHERE balearic_and_downtempo = true) AS t17,
                        (SELECT count(*) AS alternative_indie_folk_punk_subs_total FROM subscriptions WHERE alternative_indie_folk_punk = true) AS t18
                    ;
                    """
                )
                subs = db_cursor.fetchone()
                db_connection.close()

                selections_l = list(selections.keys())
                result_subs = dict()
                for i in range(len(selections_l)):
                    result_subs[f"{selections_l[i]}_subs_active"] = subs[i]
                for i in range(len(selections_l)):
                    result_subs[f"{selections_l[i]}_subs_total"] = subs[len(selections_l) + i]

                return jsonify(
                    {
                        "status": responses[200],
                        "status_code": 200,
                        "message": {
                            "result": {
                                "users": result_users,
                                "subs": result_subs
                            }
                        }
                    }
                )
        except Exception as e:
            api.abort(500, e.__doc__, status=responses[500], status_сode=500)


@api.route("/new_release")
class NewRelease(Resource):
    @api.doc(
        responses=responses,
        body=api.model(
            "API waits for new release notification from parser",
            {
                "redeye_id": fields.Integer(
                    description="Release's Redeye ID",
                    required=True
                ),
                "table": fields.String(
                    description="Table where release info was stored",
                    required=True
                )
            }
        )
    )
    def post(self):
        """API waits for new release notification from parser"""
        try:
            redeye_id = request.json["redeye_id"]
            table = request.json["table"]

            db_connection = sqlite3.connect(DB_PATH)
            db_cursor = db_connection.cursor()
            db_cursor.execute(
                f"""
                    SELECT item, samples, selection FROM {table} WHERE redeye_id = ?
                ;
                """, (redeye_id,)
            )
            item, samples, selection = db_cursor.fetchone()

            db_cursor.execute(
                f"""
                    SELECT users.user_chat_id
                    FROM users
                    JOIN subscriptions ON subscriptions.user_id = users.user_id
                    WHERE subscriptions.{selection} = true AND users.is_active = true
                ;
                """
            )
            users = [user_chat_id[0] for user_chat_id in db_cursor.fetchall()]

            if not bool(users):
                pass
            else:
                reply_markup = None
                if bool(samples):
                    samples = samples.split(",")
                    count = len(samples)
                    if count == 1:
                        reply_markup = InlineKeyboardMarkup()
                        button_a = InlineKeyboardButton(text="PLAY A", url=samples[0])
                        reply_markup.add(button_a)
                    if count == 2:
                        reply_markup = InlineKeyboardMarkup(row_width=2)
                        button_a = InlineKeyboardButton(text="PLAY A", url=samples[0])
                        button_b = InlineKeyboardButton(text="PLAY B", url=samples[1])
                        reply_markup.add(button_a, button_b)
                    if count == 3:
                        reply_markup = InlineKeyboardMarkup(row_width=3)
                        button_a = InlineKeyboardButton(text="PLAY A", url=samples[0])
                        button_b = InlineKeyboardButton(text="PLAY B", url=samples[1])
                        button_c = InlineKeyboardButton(text="PLAY C", url=samples[2])
                        reply_markup.add(button_a, button_b, button_c)
                    if count == 4:
                        reply_markup = InlineKeyboardMarkup(row_width=4)
                        button_a = InlineKeyboardButton(text="PLAY A", url=samples[0])
                        button_b = InlineKeyboardButton(text="PLAY B", url=samples[1])
                        reply_markup.add(button_a, button_b)
                        button_c = InlineKeyboardButton(text="PLAY C", url=samples[2])
                        button_d = InlineKeyboardButton(text="PLAY D", url=samples[3])
                        reply_markup.add(button_c, button_d)
                    else:
                        pass

                for user_chat_id in users:
                    try:
                        bot.send_message(user_chat_id, item, reply_markup=reply_markup, parse_mode="Markdown")
                    except ApiException as e:
                        if "bot was blocked by the user" in e.args[0]:
                            db_cursor.execute(
                                """
                                    UPDATE users
                                    SET is_active = false
                                    WHERE user_chat_id = ?
                                ;
                                """, (user_chat_id,)
                            )
                            db_connection.commit()

            db_connection.close()

            return jsonify(
                {
                    "status": responses[200],
                    "status_code": 200,
                    "message": {
                        "result": "OK"
                    }
                }
            )

        except Exception as e:
            api.abort(500, e.__doc__, status=responses[500], status_сode=500)
