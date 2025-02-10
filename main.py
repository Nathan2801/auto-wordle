import logging

from os import path
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.DEBUG)
for handler in logging.root.handlers:
    handler.addFilter(logging.Filter(__name__))
l = logging.getLogger(__name__)

""" NOTE: The following three functions return other functions
    to work nicely with the filter function.
"""
def not_equal(x):
    """ Returns whether x != y.
    """
    def inner(y):
        return x != y
    return inner

def contains(x):
    """ Returns whehter x in y.
    """
    def inner(y):
        return x in y
    return inner

def not_contains(x):
    """ Return wheter x not in y.
    """
    def inner(y):
        return x not in y
    return inner

def words_from_file(file):
    """ Returns lines of {file}, assume the file contains
        one word per line.
    """
    with open(file, "r") as file:
        return list(map(lambda s: s.strip(), file.readlines()))

class Bot:
    """ Bot is responsible for knowing all words, make attempts,
        and filter words based on the game feedback, simulating a
        real player.
    """
    def __init__(self, game, words):
        self._game = game
        self._words = words

    def _choose_word(self):
        """ Simply return the first word of the list.
        """
        if len(self._words) == 0:
            raise Exception("bot has no idea")
        return self._words.pop(0)

    def _filter_words(self, feedback):
        """ Filter words based on the feedback.
        """
        letters = {}
        corrects = {}
        # Setup values for filtering
        for i in range(len(feedback)):
            letter = feedback[i][0]
            status = feedback[i][1]
            if letter not in letters:
                letters[letter] = 0
            if status == "present":
                letters[letter] += 1
            elif status == "correct":
                letters[letter] += 1
                if not letter in corrects:
                    corrects[letter] = []
                corrects[letter].append(i)
        # Filter words by letters count.
        for letter, count in letters.items():
            method_ = None
            if count == 0:
                method_ = lambda w: w.count(letter) == 0
            else:
                method_ = lambda w: w.count(letter) >= count
            filter_ = filter(method_, self._words)
            self._words = list(filter_)
        # Filter words by the correct letters.
        for letter, positions in corrects.items():
            for position in positions:
                method_ = lambda w: w[position] == letter
                filter_ = filter(method_, self._words)
                self._words = list(filter_)

    def play(self):
        """ Simulate the player experience.
        """
        word = self._choose_word(); l.info(f"attempt: {word}")
        feed = self._game.attempt(word)
        if self._game.won(feed):
            return l.info(f"correct word: {word}")
        size = len(self._words)
        self._filter_words(feed)
        l.info(f"filtered {size - len(self._words)} words")
        return self.play()

class Wordle:
    """ Wordle class is responsible for controlling the wordle page
        and retrieving any usefull information.
    """
    def __init__(self, driver, max_attempts=6, timeout=5):
        self._driver = driver 
        self._wait = WebDriverWait(driver, timeout)

        self._attempt = 0
        self._max_attempts = max_attempts

    def _wait_and_click(self, locator):
        """ Uses {WebDriverWait} located at {self._wait} to wait an element
            to be clickable, then click it.
        """
        try:
            self._wait.until(EC.element_to_be_clickable(locator)).click()
            return True
        except:
            return False

    def setup(self):
        """ Perform necessary operations to get the game running.
        """
        l.info("setup initialized")
        # Reject cookies
        if not self._wait_and_click((By.XPATH, "//button[text()=\"Reject all\"]")):
            l.warning("unable to reject all cookies")
        # Accept terms
        if not self._wait_and_click((By.XPATH, "//button[text()=\"Continue\"]")):
            l.warning("unable to accept terms")
        # Click play
        if not self._wait_and_click((By.XPATH, "//button[text()=\"Play\"]")):
            l.warning("unable to click play")
        # Close instructions
        if not self._wait_and_click((By.XPATH, "//button[@aria-label=\"Close\"]")):
            l.warning("unable to close instructions")
        # Make sure setup is correct
        try:
            sleep(0.5) # Wait game page load
            _ = self._driver.find_element(By.ID, "wordle-app-game")
            # Scroll to game
            ActionChains(self._driver)\
            .scroll_by_amount(0, +999)\
            .perform()
        except Exception as e:
            raise Exception("setup failed") from e
        l.info("setup finished")

    @staticmethod
    def _parse_feedback(feedback):
        """ Parses the feedback from the boxes with letters
            in the page. Input example: "1st letter, A, absent".
        """
        args = feedback.split(",")
        if len(args) < 3:
            raise Exception("missing feedback")
        letter = args[1].strip().lower()
        status = args[2].split(" ")[1].strip()
        return [letter, status]

    def _get_word_feedback(self):
        """ Get row containing the boxes with letters in the game.
        """
        return self._driver.find_elements(By.XPATH, f"//div[@aria-label=\"Row {self._attempt}\"]/div/div")

    def attempt(self, word):
        """ Perform necessary actions to make an attempt in the
            game.
        """
        if len(word) != 5:
            raise Exception(f"invalid word length: {word}")
        # Check if we run out attempts.
        self._attempt += 1
        if self._attempt > self._max_attempts:
            raise Exception("game is over")
        # Enter word
        ActionChains(self._driver)\
        .send_keys(word + Keys.ENTER)\
        .perform()
        sleep(2) # Wait word to be processed.
        # Obtain feedback and returns it.
        feedback = []
        letters = self._get_word_feedback()
        for letter in letters:
            feedback_ = Wordle._parse_feedback(letter.get_attribute("aria-label"))
            feedback.append(feedback_)
        return feedback

    @staticmethod
    def won(feedback):
        """ Helper to check whether we won based on feedback.
        """
        for [_, status] in feedback:
            if status != "correct":
                return False
        return True

def main():
    driver = webdriver.Chrome()
    driver.get("https://www.nytimes.com/games/wordle/index.html")

    wordle = Wordle(driver)
    wordle.setup()

    here = path.dirname(__file__)
    words = words_from_file(here + "/dictionary.txt")
    bot = Bot(wordle, words)

    try:
        bot.play()
    except Exception as e:
        l.error(e)
    finally:
        driver.close()
    return 0

if __name__ == "__main__":
    exit(main())
