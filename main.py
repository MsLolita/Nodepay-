import asyncio
import sys
from core.utils.logger import logger

def check_tkinter_available():
    try:
        import customtkinter
        return True
    except ImportError:
        return False

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        if check_tkinter_available():
            logger.info("Starting GUI version...")
            import customtkinter as ctk
            from customtkinter_gui import BotGUI

            root = ctk.CTk()
            app = BotGUI(root)
            app.setup_logger()
            root.mainloop()
        else:
            logger.info("Starting console version...")
            from core.menu import ConsoleMenu
            menu = ConsoleMenu()
            asyncio.run(menu.run())
                
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
