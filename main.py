from AutoBrowser import AutoBrowser
from time import sleep
import platform
import random

print(platform.system())
browser = AutoBrowser()
browser.OpenWebsite('https://en.tribalwars2.com/page#/')
users = browser.user_list

'''
if browser.FindElementXPATH(browser.username_input):
    browser.TextInput(browser.username_input, users[0])
    browser.TextInput(browser.password_input, 'tsx0711lo')
    browser.ClickElement(browser.login_button)
'''

if browser.FindElementXPATH(browser.register_button):
    browser.Script('jumpToRegister();')
    browser.TextInput(browser.register_user_input, 'Apexea')
    browser.TextInput(browser.register_password_input, 'tsx0711lo')
    browser.TextInput(browser.register_email_input, f'apexea{random.randint(1000, 9999)}@example.com')
    browser.ClickElement(browser.register_accept)
    browser.ClickElement(browser.register_submit)

sleep(10)
browser.CloseBrowser()