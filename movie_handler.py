import aiohttp
import typing as tp
from bs4 import BeautifulSoup
import asyncio
import re
from aiogram import html
from operator import add
from functools import reduce


class NoSuchMovieException(Exception):
    pass


headers: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 "
                  "(Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}


class MovieMetadata:
    def __init__(self,
                 title: str | None, description: str | None, country: str | None,
                 year: str | None, rating: float | None):
        len_flag = 1
        if description is not None:
            description = reduce(add, [' ' + s.strip().capitalize() for s in re.split("(?<=[.])", description)])
            description.strip()
            len_flag = 0
        self.title = title
        self.description = description
        self.country = country
        self.year = year
        self.rating = rating
        self.priority = 6 - (title is None) - len_flag * 2 - (country is None) - (year is None)
        if rating is None or rating < 1:
            self.rating = None
            self.priority -= 1

    def __str__(self):
        return (f"{html.bold(self.title)}\n\n"
                * (self.title is not None) +
                f"{html.underline(html.italic('Описание:'))} {self.description}\n\n"
                * (self.description is not None) +
                f"{html.italic('Страна:')} {self.country}\n\n"
                * (self.country is not None) +
                f"{html.italic('Год выпуска:')} {self.year}\n\n"
                * (self.year is not None) +
                f"{html.italic('Рейтинг IMDB:')}\n {self.rating}\n\n"
                * (self.rating is not None))


class MovieHandler:

    @staticmethod
    async def _parse_string(data: str) -> MovieMetadata:
        data.strip()
        try:
            description = data.index('это')
        except ValueError:
            description = 0
        try:
            name = data.index('Название:')
        except ValueError:
            try:
                name = data.index('Название (Eng):')
            except ValueError:
                name = 0 if description != 0 else None
        try:
            country = data.index('Страна:')
        except ValueError:
            # print('Страна не найдена')
            country = 0
        try:
            end_country = data.index('Режиссер:')
        except ValueError:
            # print('Режиссер не найден')
            end_country = 0
        try:
            year = data.index('Год выхода:')
        except ValueError:
            # print('Год не найден')
            year = None
        try:
            raiting = data.index('Актеры:') - 3
        except ValueError:
            # # print('Рейтинг не найден')
            raiting = 0
        try_name = (data[name + 9:year].strip()
                    if year is not None else data[name + 9:country].strip()
                    if name != 0 else data[name:description].strip()[:-1]
                    if name is not None and country is not None else None)
        if name == 0 and "Фильм" in try_name:
            try_name = try_name[:try_name.index("Фильм")]

        return MovieMetadata(
            try_name,
            (data[description:name].strip().capitalize()
             if name is not None and name != 0 else data[description:country].strip().capitalize()),
            data[country + 7:end_country].strip(),
            data[year + 11:country].strip() if year is not None else None,
            float(data[raiting:raiting + 3]) if raiting != 0 else None
        )

    @staticmethod
    async def _parse_info(url: str) -> tp.Optional[MovieMetadata]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        print(f"Ошибка запроса: {resp.status}")
                        return None
                    content = await resp.text()
            soup = BeautifulSoup(content, 'html.parser')

            video_section = soup.find('div', id='video-description')
            if video_section:
                description = video_section.get_text(strip=True)
                # print(description)
                return await MovieHandler._parse_string(description)

            fleft_div = soup.find('div', class_='fleft fx-1 fx-row')
            if fleft_div:
                fleft_text = fleft_div.get_text(strip=True)
                # print(fleft_text)
                return await MovieHandler._parse_string(fleft_text)

            raise NoSuchMovieException("Не удалось найти необходимую секцию на странице.")

        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return None

    @staticmethod
    async def get_links_by_query(search_query: str) -> tuple[list[str], MovieMetadata | None]:
        url = 'https://www.google.com/search'
        parameters = {'q': search_query + ' смотреть онлайн lordfilm'}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=parameters, headers=headers) as resp:
                    if resp.status != 200:
                        # print(f"Ошибка запроса: {resp.status}")
                        return [], None
                    content = await resp.text()

            soup = BeautifulSoup(content, 'html.parser')

            search = soup.find(id='search')
            if not search:
                # print("Не удалось найти секцию результатов поиска.")
                return [], None

            links = [
                tag['href']
                for tag in search.find_all('a', href=True)
                if tag['href'].startswith('http') and 'lordfilm' in tag['href']
            ]
            link_set = set()
            max_prioity = -5
            main_meta = MovieMetadata(
                search_query,
                None,
                None,
                None,
                None
            )
            for link in links:
                try:
                    if (tmp := await asyncio.wait_for(MovieHandler._parse_info(link), timeout=1)) is not None:
                        if max_prioity < tmp.priority:
                            if tmp.title is None:
                                tmp.title = search_query.capitalize()
                            max_prioity = tmp.priority
                            main_meta = tmp
                        link_set.add(link)
                        if len(link_set) == 3:
                            break
                except asyncio.TimeoutError:
                    if 'anime' in link:
                        tmp_meta = MovieMetadata(
                            search_query.capitalize(),
                            ('А ловко ты это придумал, РКН заблокировал аниме '
                             'в рф, об этом было предупреждение при команде /start.\n'
                             + html.spoiler('Ладно, так уж и быть я кое-что для тебя нашёл')),
                            None,
                            None,
                            None
                        )
                        link_set.add(link)
                        if max_prioity < 2:
                            max_prioity = 2
                            main_meta = tmp_meta

            return list(link_set) if len(link_set) != 0 else [links[0]], main_meta

        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return [], None
