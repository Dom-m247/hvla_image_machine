#this is gonna be stupid and i'll hate it but whatever
##most likely to get thrown out :P
#from selenium import webdriver
#from selenium.webdriver.firefox.service import Service
#from selenium.webdriver.firefox.options import Options
##from selenium.exceptions import * 
#
#def setup_selenium():
#    """Set up Selenium WebDriver."""
#  
#
#    geckoDriver_options = Options()
#    geckoDriver_options.add_argument("--headless")  # Run in headless mode
#    geckoDriver_options.add_argument("--no-sandbox")
#    geckoDriver_options.add_argument("--disable-dev-shm-usage")
#
#    # Specify the path to chromedriver if necessary
#    service = Service()  # Add path to chromedriver if not in PATH
#
#    driver = webdriver.geckoDriver(service=service, options=geckoDriver_options)
#    return driver
#
#def teardown(driver):
#    driver.quit()
#
#def start_dowload(target):
#
#    """Main entry to find and begin download. Exits on completion."""
#    print(f"Starting download for target: {target}")
#    driver = setup_selenium()
#    try:
#        
#        # Add logic to interact with the page and start download
#        print("Download initiated.")
#    except Exception as e:
#        print(f"An error occurred: {e}")
#    finally:
#        teardown(driver)