import discord
from discord import app_commands

import datetime
import re

BOT_TOKEN = "YOUR_BOT_TOKEN"

class bot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.user_pending_reaction = set()
    async def on_ready(self):
        await self.tree.sync()
        print(f"Logged in as {self.user}!")

bot = bot(intents=discord.Intents.default())
user_data = {}

# 時給の設定
@bot.tree.command(name="wage", description="時給を設定する")
async def set_hourly(interaction: discord.Interaction, hourly: int):
    user_id = interaction.user.id
    if user_id not in user_data:
       user_data[user_id] = {}
    user_data[user_id]["hourly"] = hourly
    await interaction.response.send_message(f"時給を{(hourly):,}円に設定しました")

# 計測開始
@bot.tree.command(name="begin", description="仕事を始める")
async def begin_work(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    if "hourly" not in user_data[user_id]:
       await interaction.response.send_message("時給が設定されていません。")
       return
    if "start_time" in user_data[user_id]:
        await interaction.response.send_message("すでに打刻されています。")
    else:
        user_data[user_id]["start_time"] = datetime.datetime.now()
        user_data[user_id]["total_rest_duration"] = datetime.timedelta()
        await interaction.response.send_message("仕事を始めます。\n行ってらっしゃい。")

# 計測の一時停止と再開
@bot.tree.command(name="rest", description="計測を一時停止または再開する")
async def rest_work(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in user_data and "start_time" in user_data[user_id]:
        if "rest_start_time" not in user_data[user_id]:
            # 一時停止
            user_data[user_id]["rest_start_time"] = datetime.datetime.now()
            await interaction.response.send_message("休憩を開始します。\n行ってらっしゃい。")
        else:
            # 一時停止を解除し，計測再開
            rest_start_time = user_data[user_id]["rest_start_time"]
            rest_duration = datetime.datetime.now() - rest_start_time
            user_data[user_id]["total_rest_duration"] += rest_duration
            del user_data[user_id]["rest_start_time"]
            await interaction.response.send_message("お帰りなさい。\n休憩を終了します。")
    else:
        await interaction.response.send_message("打刻されていません。")

# 計測終了，および賃金の計算
@bot.tree.command(name="finish", description="仕事を終える")
async def finish_work(interaction: discord.Interaction):
    user_id = interaction.user.id
    hourly = user_data[user_id]["hourly"]
    if user_id in user_data and "start_time" in user_data[user_id]:

        # `/rest`コマンドの途中であればリアクションによる確認を行う
        if "rest_start_time" in user_data[user_id]:
            await interaction.response.defer()
            message = await interaction.followup.send("まだ休憩中です。\n作業時間の計測を終了してよろしいですか？")
            await message.add_reaction("🇾")
            await message.add_reaction("🇳")

            bot.user_pending_reaction.add(user_id)

            def check(reaction, user):
                return user == interaction.user and str(reaction.emoji) in ["🇾", "🇳"]

            reaction, user = await bot.wait_for("reaction_add", check=check)
            bot.user_pending_reaction.remove(user_id)

            # Yを選ぶとそのまま計測を終了する
            if str(reaction.emoji) == "🇾":
                finish_time = datetime.datetime.now()
                start_time = user_data[user_id]["start_time"]
                total_rest_duration = user_data[user_id].get("total_rest_duration", datetime.timedelta())
                
                elapsed_time = finish_time - start_time - total_rest_duration
                seconds = int(elapsed_time.total_seconds())
                total_wage = (seconds / 3600) * hourly
                elapsed_str = f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
                total_wage_formatted = "{:,.2f}".format(total_wage)
                await interaction.followup.send(
                    (
                     f"{interaction.user.mention} お疲れ様です。\n"
                     f"時給: {(hourly):,}円\n"
                     f"今回の作業時間: {elapsed_str}\n"
                     f"今回分の賃金: {total_wage_formatted}円\n"
                     f"`[finish]`"
                    )
                )
                del user_data[user_id]["start_time"]
                del user_data[user_id]["total_rest_duration"]
                if "rest_start_time" in user_data[user_id]:
                    del user_data[user_id]["rest_start_time"]

            # Nを選ぶと`/finish`をキャンセルして休憩を再開する
            elif str(reaction.emoji) == "🇳":
                await interaction.followup.send("休憩を再開します。")
        else:
            finish_time = datetime.datetime.now()
            start_time = user_data[user_id]["start_time"]
            total_rest_duration = user_data[user_id].get("total_rest_duration", datetime.timedelta())
            
            elapsed_time = finish_time - start_time - total_rest_duration
            seconds = int(elapsed_time.total_seconds())
            total_wage = (seconds / 3600) * hourly
            elapsed_str = f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
            total_wage_formatted = "{:,.2f}".format(total_wage)
            await interaction.response.send_message(
                (
                 f"{interaction.user.mention} お疲れ様です。\n"
                 f"時給: {(hourly):,}円\n"
                 f"今回の作業時間: {elapsed_str}\n"
                 f"今回分の賃金: {total_wage_formatted}円\n"
                 f"`[finish]`"
                )
            )
            del user_data[user_id]["start_time"]
            del user_data[user_id]["total_rest_duration"]
            if "rest_start_time" in user_data[user_id]:
                del user_data[user_id]["rest_start_time"]
    else:
        await interaction.response.send_message("打刻されていません。")

# 手動で作業時間を入力し，給料を設定する
@bot.tree.command(name="fix", description="手動で作業時間を設定し，指定した`/finish`または`/fix`コマンドを削除する（オプション）")
@app_commands.describe(hours="作業時間（時）", minutes="作業時間（分）", message_link="削除するメッセージのリンク（オプション）")
async def fix_work(interaction: discord.Interaction, hours: int, minutes: int, message_link: str = None):
    user_id = interaction.user.id
    hourly = user_data[user_id]["hourly"]
    if user_id not in user_data or "hourly" not in user_data[user_id]:
        await interaction.response.send_message("時給が設定されていません。")
        return
    try:
        if message_link is not None and message_link.strip():  # リンクが存在し，空白でない場合に処理を行う
            try:
                message_id = int(message_link.split("/")[-1])
                channel_id = int(message_link.split("/")[-2])
                channel = bot.get_channel(channel_id)
                message_to_delete = await channel.fetch_message(message_id)
                id_code = ["[finish]", "[fix]"]

                if message_to_delete.author == bot.user:
                    if any(code in message_to_delete.content for code in id_code):
                        if interaction.user.mention in message_to_delete.content:
                            await message_to_delete.delete()
                        else:
                            await interaction.response.send_message("指定されたメッセージは他のユーザーのものです。削除できません。")
                            return
                    else:
                        await interaction.response.send_message("指定されたメッセージは`/finish`または`/fix`コマンドではありません。")
                        return
                else:
                    await interaction.response.send_message("指定されたメッセージは他のユーザーによって送信されたものです。")
                    return
            except (discord.NotFound, ValueError, IndexError):
                await interaction.response.send_message("指定されたメッセージが見つかりませんでした。リンクが正しいことを確認してください。")
                return

        # 以降はそのまま計算
        try:
            elapsed_time = datetime.timedelta(hours=hours, minutes=minutes)
            seconds = int(elapsed_time.total_seconds())
            elapsed_str = f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
        
            total_wage = (seconds / 3600) * hourly
            total_wage_formatted = "{:,.2f}".format(total_wage)
        
            await interaction.response.send_message(
                (
                f"{interaction.user.mention} 以下の内容で修正します:\n"
                f"時給: {(hourly):,}円\n"
                f"今回の作業時間: {elapsed_str}\n"
                f"今回分の賃金: {total_wage_formatted}円\n"
                f"`[fix]`"
                )
            )
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {str(e)}")

    except Exception as e:
        await interaction.followup.send(f"エラーが発生しました: {str(e)}")


# 1日分の作業時間と給料を計算する
@bot.tree.command(name="daily", description="指定された日の午前6:00から翌朝の午前5:59までの間の作業時間と合計賃金を計算する")
async def daily_sum_work(interaction: discord.Interaction, month: int, day: int):
    user_id = interaction.user.id
    if user_id not in user_data or "hourly" not in user_data[user_id]:
        await interaction.response.send_message("時給が設定されていません。")
        return
    
    hourly = user_data[user_id]["hourly"]
    user_mention = interaction.user.mention
    channel = interaction.channel
    id_code = ["[finish]", "[fix]"]

    total_wage = 0.0
    total_seconds = 0
    time_pattern = re.compile(r"今回の作業時間: (\d+):(\d{2}):(\d{2})")
    wage_pattern = re.compile(r"今回分の賃金: ([\d,]+\.\d{2})円")
    
    # 現在の年を取得（年内のものを検索するため）
    current_year = datetime.datetime.now().year
    
    # 指定された日の午前6:00から次の日の午前5:59までの範囲を設定
    start_time = datetime.datetime(current_year, month, day, 6, 0, 0)
    end_time = start_time + datetime.timedelta(hours=23, minutes=59, seconds=59)

    
    # 指定された範囲内のメッセージを検索
    async for message in channel.history(limit=1000, after=start_time, before=end_time):
        if message.author == bot.user and user_mention in message.content and any(code in message.content for code in id_code):
            wage_match = wage_pattern.search(message.content)
            time_match = time_pattern.search(message.content)
            if wage_match:
                extracted_wage = wage_match.group(1).replace(",", "")
                total_wage += float(extracted_wage)
            if time_match:
                hours, minutes, seconds = map(int, time_match.groups())
                total_seconds += hours * 3600 + minutes * 60 + seconds
    
    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60
    total_seconds_remaining = total_seconds % 60
    elapsed_str = f"{total_hours}:{total_minutes:02d}:{total_seconds_remaining:02d}"
    
    total_wage_formatted = "{:,.2f}".format(total_wage)
    await interaction.response.send_message(
        (
        f"{user_mention}の{current_year}/{month:02}/{day:02}の仕事内容:\n"
        f"現在時給: {(hourly):,}円\n"
        f"合計作業時間: {elapsed_str}\n"
        f"合計賃金: {total_wage_formatted}円"
        )
    )

# これまでの作業時間と賃金を計算する
@bot.tree.command(name="sum", description="これまでの作業時間と賃金を計算する")
async def sum_work(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in user_data or "hourly" not in user_data[user_id]:
        await interaction.response.send_message("時給が設定されていません。")
        return
    hourly = user_data[user_id]["hourly"]
    user_mention = interaction.user.mention
    channel = interaction.channel
    id_code = ["[finish]", "[fix]"]

    total_wage = 0.0
    total_seconds = 0
    time_pattern = re.compile(r"今回の作業時間: (\d+):(\d{2}):(\d{2})")
    wage_pattern = re.compile(r"今回分の賃金: ([\d,]+\.\d{2})円")
    
    # チャンネルのメッセージ履歴から情報を取得
    async for message in channel.history(limit=1000):
        if message.author == bot.user and user_mention in message.content and any(code in message.content for code in id_code):
            wage_match = wage_pattern.search(message.content)
            time_match = time_pattern.search(message.content)
            if wage_match:
                extracted_wage = wage_match.group(1).replace(",", "")
                total_wage += float(extracted_wage)
            if time_match:
                hours, minutes, seconds = map(int, time_match.groups())
                total_seconds += hours * 3600 + minutes * 60 + seconds
    
    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60
    total_seconds_remaining = total_seconds % 60
    elapsed_str = f"{total_hours}:{total_minutes:02d}:{total_seconds_remaining:02d}"
    
    total_wage_formatted = "{:,.2f}".format(total_wage)
    await interaction.response.send_message(
        (
        f"{user_mention}のこれまでの仕事内容:\n"
        f"現在の時給: {(hourly):,}円\n"
        f"合計作業時間: {elapsed_str}\n"
        f"合計賃金: {total_wage_formatted}円"
        )
    )

# これまでの作業記録をリセットする
@bot.tree.command(name="reset", description="これまでの作業記録をリセットする")
async def reset_messages(interaction: discord.Interaction):
    user_mention = interaction.user.mention
    channel = interaction.channel

    # 確認メッセージを表示
    await interaction.response.defer()
    message = await interaction.followup.send("本当にこれまでの作業記録をリセットしますか？\nこれまでの`/finish`と`/fix`のログがすべて削除されます。")
    await message.add_reaction("🇾")
    await message.add_reaction("🇳")

    # リアクションで判別
    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ["🇾", "🇳"]

    reaction, user = await bot.wait_for("reaction_add", check=check)

    # Nを選ぶとキャンセル
    if str(reaction.emoji) == "🇳":
        await interaction.followup.send("リセットをキャンセルしました。")
        return

    # 先に合計作業時間と合計賃金が計算される
    total_wage = 0.0
    total_seconds = 0
    time_pattern = re.compile(r"今回の作業時間: (\d+):(\d{2}):(\d{2})")
    wage_pattern = re.compile(r"今回分の賃金: ([\d,]+\.\d{2})円")

    deleted_count = 0
    
    # チャンネルのメッセージ履歴から対象のメッセージを検索して削除
    async for message in channel.history(limit=1000):  # 1000件を取得
        if message.author == bot.user and user_mention in message.content:
            if "[finish]" in message.content or "[fix]" in message.content:
                if wage_match := wage_pattern.search(message.content):
                    extracted_wage = wage_match.group(1).replace(",", "")
                    total_wage += float(extracted_wage)
                if time_match := time_pattern.search(message.content):
                    hours, minutes, seconds = map(int, time_match.groups())
                    total_seconds += hours * 3600 + minutes * 60 + seconds
                try:
                    await message.delete()
                    deleted_count += 1
                except discord.NotFound:
                    pass

    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60
    total_seconds_remaining = total_seconds % 60
    elapsed_str = f"{total_hours}:{total_minutes:02d}:{total_seconds_remaining:02d}"

    total_wage_formatted = "{:,.2f}".format(total_wage)
    await interaction.followup.send(
        f"これまでのコマンドを削除し、{user_mention} の合計作業時間（{elapsed_str}）と合計賃金（{total_wage_formatted}円）をリセットしました。"
    )

bot.run(BOT_TOKEN)
