from art import text2art
from termcolor import colored
import configparser
import os

from core.captcha import ServiceCapmonster
from core.utils.logger import logger
from core.utils.bot import Bot

class ConsoleMenu:
    def __init__(self, config_file="data/settings.ini"):
        logger.info("Initializing console menu (GUI not available)")
        self.CONFIG_FILE = config_file
        self.config = self.load_config()

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(self.CONFIG_FILE):
            config.read(self.CONFIG_FILE)
        else:
            config['DEFAULT'] = {
                'AccountsFile': '',
                'ProxiesFile': '',
                'ReferralCodes': '',
                'Threads': '5',
                'CaptchaService': 'capmonster',
                'CaptchaAPIKey': '',
                'DelayMin': '1',
                'DelayMax': '2'
            }
        return config

    def validate_config(self):
        required_fields = {
            'AccountsFile': 'Accounts file path',
            'ProxiesFile': 'Proxies file path',
            'CaptchaAPIKey': 'Captcha API key'
        }
        
        for field, name in required_fields.items():
            if not self.config['DEFAULT'].get(field):
                logger.error(f"Error: {name} not configured in {self.CONFIG_FILE}")
                return False
            if not os.path.exists(self.config['DEFAULT'][field]) and field.endswith('File'):
                logger.error(f"Error: {name} does not exist: {self.config['DEFAULT'][field]}")
                return False
        
        try:
            threads = int(self.config['DEFAULT']['Threads'])
            if threads <= 0:
                raise ValueError
        except ValueError:
            logger.error("Error: Number of threads must be a positive integer!")
            return False

        try:
            delay_min = float(self.config['DEFAULT']['DelayMin'])
            delay_max = float(self.config['DEFAULT']['DelayMax'])
            if delay_min < 0 or delay_max < 0 or delay_min > delay_max:
                raise ValueError
        except ValueError:
            logger.error("Error: Invalid delay range! Please enter valid positive numbers, with min <= max.")
            return False

        return True

    def print_menu(self):
        print("\n" + "="*50)
        print(colored(text2art("NodePay Bot", font="small"), "blue"))
        print(colored("1. Register Accounts", "cyan"))
        print(colored("2. Start Farm", "cyan"))
        print(colored("3. View Settings", "cyan"))
        print(colored("4. Exit", "cyan"))
        print("="*50 + "\n")

    async def handle_bot_action(self, choice):
        settings = self.config['DEFAULT']
        ref_codes = [code.strip() for code in settings['ReferralCodes'].split(',') if code.strip()]
        
        bot = Bot(
            account_path=settings['AccountsFile'],
            proxy_path=settings['ProxiesFile'],
            threads=int(settings['Threads']),
            ref_codes=ref_codes,
            captcha_service=ServiceCapmonster(api_key=settings['CaptchaAPIKey']),
            delay_range=(float(settings['DelayMin']), float(settings['DelayMax']))
        )

        try:
            if choice == "1":
                logger.info("Starting account registration...")
                await bot.start_registration()
            else:
                logger.info("Starting farming...")
                await bot.start_mining()
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
            bot.stop()
        except Exception as e:
            logger.error(f"Error occurred: {e}")

    def show_settings(self):
        print("\nCurrent Settings:")
        for key, value in self.config['DEFAULT'].items():
            print(colored(f"{key}: {value}", "green"))

    async def run(self):
        while True:
            self.print_menu()
            choice = input("Enter your choice: ").strip()
            if choice == '4':
                logger.info("Exiting.")
                break
            elif choice in ['1', '2', '3']:
                if not self.validate_config():
                    logger.error("Invalid configuration. Please check your settings.")
                    continue
                await self.handle_bot_action(choice)
            else:
                logger.warning("Invalid choice. Please enter a valid option.")
