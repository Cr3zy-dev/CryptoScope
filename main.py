#!/usr/bin/env python3
"""
CryptoScope v1.0.0 - Professional Cryptocurrency Analysis Platform
"""

import requests
import json
import time
import os
import sys
from datetime import datetime
import random
from fuzzywuzzy import fuzz # Import fuzz
from fuzzywuzzy import process # Import process for easier top N matching

# --- COLOR HANDLING ---
class Colors:
    # Standard ANSI colors for maximum compatibility
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    PURPLE = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'
    
    # Bright versions for better visibility
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_PURPLE = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    @staticmethod
    def init_colors():
        """
        Initializes color support, specifically for Windows.
        Tries colorama first, then direct ctypes for ANSI.
        """
        if os.name == 'nt': # Windows
            try:
                import colorama
                colorama.init()
            except ImportError:
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 0x0004) # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                except Exception as e:
                    pass # Fail silently if ctypes or API call fails for now

# Initialize colors as early as possible
Colors.init_colors()

class CryptoScope:
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.analysis_count = 0
        self.last_api_call_time = 0
        self.api_call_delay = 1.5 # seconds delay between API calls to avoid hitting rate limits
        self.all_coin_ids = [] # To store all valid coin IDs and names for suggestions
        self.load_all_coins() # Load coin list at startup

    def clear_screen(self):
        """Clears the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_banner(self):
        """Prints the application banner."""
        banner = f'''
{Colors.RED}{Colors.BOLD}  
 MM'""""'YMM                              dP            
 M' .mmm. `M                              88            
 M  MMMMMooM 88d888b. dP    dP 88d888b. d8888P .d8888b. 
 M  MMMMMMMM 88'  `88 88    88 88'  `88   88   88'  `88 
 M. `MMM' .M 88       88.  .88 88.  .88   88   88.  .88 
 MM.     .dM dP       `8888P88 88Y888P'   dP   `88888P'  Scope v1.0.0
 MMMMMMMMMMM               .88 88                       
                       d8888P  dP {Colors.END}
{Colors.CYAN}                  Advanced Crypto Tracker
                 !!!NOT FINANCIAL ADVICE!!!{Colors.END}
'''
        print(banner)

    def load_all_coins(self):
        """
        Fetches the complete list of cryptocurrency IDs and names from CoinGecko.
        This list is used for the "Did you mean?" suggestion feature.
        """
        print(f"{Colors.GRAY}[-] Loading complete coin list for suggestions (this may take a moment)...{Colors.END}")
        list_url = f"{self.base_url}/coins/list"
        try:
            response = requests.get(list_url, timeout=20) # Increased timeout for large list
            if response.status_code == 200:
                self.all_coin_ids = response.json()
                print(f"{Colors.BRIGHT_GREEN}[+] Loaded {len(self.all_coin_ids)} coins for suggestions.{Colors.END}")
            else:
                print(f"{Colors.BRIGHT_RED}[-] Failed to load coin list for suggestions (Status: {response.status_code}).{Colors.END}")
                self.all_coin_ids = [] # Ensure it's empty on failure
        except requests.exceptions.Timeout:
            print(f"{Colors.BRIGHT_RED}[-] Network Error: Timeout while loading coin list.{Colors.END}")
            self.all_coin_ids = []
        except requests.exceptions.ConnectionError:
            print(f"{Colors.BRIGHT_RED}[-] Network Error: No internet connection while loading coin list.{Colors.END}")
            self.all_coin_ids = []
        except json.JSONDecodeError:
            print(f"{Colors.BRIGHT_RED}[-] Data Error: Failed to decode coin list JSON.{Colors.END}")
            self.all_coin_ids = []
        except Exception as e:
            print(f"{Colors.RED}[-] An unexpected error occurred while loading coin list: {str(e)}{Colors.END}")
            self.all_coin_ids = []

    def suggest_coin_id(self, incorrect_id, limit=3, score_threshold=70):
        """
        Suggests correct coin IDs based on a fuzzy match with the incorrect input.
        """
        if not self.all_coin_ids:
            return [] # No list to search from

        all_suggestions = {} # Use a dictionary to store unique (id, name) tuples with their highest score

        # Create separate lists for IDs and Names to search against
        coin_id_strings = [coin['id'] for coin in self.all_coin_ids]
        coin_name_strings = [coin['name'] for coin in self.all_coin_ids]

        # Search against coin IDs
        # process.extract returns (match_string, score)
        id_matches = process.extract(incorrect_id, coin_id_strings, scorer=fuzz.ratio, limit=limit * 2)
        for match_id, score in id_matches:
            if score >= score_threshold:
                # Find the original coin object using the matched ID
                original_coin = next((coin for coin in self.all_coin_ids if coin['id'] == match_id), None)
                if original_coin:
                    # Store as (ID, Name) and update score if a better match is found for the same coin
                    all_suggestions[(match_id, original_coin['name'])] = max(all_suggestions.get((match_id, original_coin['name']), 0), score)

        # Search against coin Names
        name_matches = process.extract(incorrect_id, coin_name_strings, scorer=fuzz.ratio, limit=limit * 2)
        for match_name, score in name_matches:
            if score >= score_threshold:
                # Find the original coin object using the matched name
                original_coin = next((coin for coin in self.all_coin_ids if coin['name'] == match_name), None)
                if original_coin:
                    # Store as (ID, Name) and update score if a better match is found for the same coin
                    all_suggestions[(original_coin['id'], match_name)] = max(all_suggestions.get((original_coin['id'], match_name), 0), score)
        
        # Sort unique suggestions by score and return the top N
        sorted_suggestions = sorted(all_suggestions.items(), key=lambda item: item[1], reverse=True)
        return [sugg_tuple for sugg_tuple, score in sorted_suggestions[:limit]]


    def _enforce_rate_limit(self):
        """Enforces a basic rate limit for API calls."""
        time_elapsed = time.time() - self.last_api_call_time
        if time_elapsed < self.api_call_delay:
            wait_time = self.api_call_delay - time_elapsed
            print(f"{Colors.GRAY}[-] Rate limit: Waiting for {wait_time:.1f} seconds...{Colors.END}")
            time.sleep(wait_time)
        self.last_api_call_time = time.time()

    def get_crypto_data(self, coin_id):
        """
        Fetches detailed cryptocurrency data from CoinGecko API for a given coin ID.
        Returns data dictionary on success, None otherwise.
        """
        self._enforce_rate_limit()
        
        try:
            url = f"{self.base_url}/coins/{coin_id}"
            params = {
                'localization': 'false', 'tickers': 'false', 'market_data': 'true',
                'community_data': 'false', 'developer_data': 'false', 'sparkline': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"{Colors.BRIGHT_RED}[-] Error: Coin '{coin_id}' not found. Please check the ID.{Colors.END}")
                # --- NEW: Suggestion logic on 404 ---
                suggestions = self.suggest_coin_id(coin_id)
                if suggestions:
                    print(f"{Colors.YELLOW}[?] Did you mean:{Colors.END}")
                    for suggested_id, suggested_name in suggestions:
                        print(f"    {Colors.YELLOW}- {suggested_name} ({suggested_id}){Colors.END}")
                # --- END NEW ---
            elif response.status_code == 429:
                print(f"{Colors.BRIGHT_RED}[-] Error: Rate limit exceeded. Please wait a moment before trying again.{Colors.END}")
            else:
                print(f"{Colors.BRIGHT_RED}[-] API Error: Received status code {response.status_code} for {coin_id}.{Colors.END}")
            return None
        except requests.exceptions.Timeout:
            print(f"{Colors.BRIGHT_RED}[-] Network Error: Request timed out while fetching data for {coin_id}.{Colors.END}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"{Colors.BRIGHT_RED}[-] Network Error: Could not connect to CoinGecko API. Check your internet connection.{Colors.END}")
            return None
        except json.JSONDecodeError:
            print(f"{Colors.BRIGHT_RED}[-] Data Error: Failed to decode JSON response for {coin_id}.{Colors.END}")
            return None
        except Exception as e:
            print(f"{Colors.RED}[-] An unexpected error occurred while fetching data for {coin_id}: {str(e)}{Colors.END}")
            return None
    
    def calculate_investment_signal(self, data):
        """
        Calculates an investment signal based on various market data points.
        Returns a dictionary with recommendation, confidence, and relevant metrics.
        """
        try:
            market_data = data['market_data']
            
            price_24h = market_data.get('price_change_percentage_24h', 0.0)
            price_7d = market_data.get('price_change_percentage_7d', 0.0)
            price_30d = market_data.get('price_change_percentage_30d', 0.0)
            
            market_cap_rank = data.get('market_cap_rank', 9999)
            current_price = market_data['current_price'].get('usd', 0.0)
            market_cap = market_data.get('market_cap', {}).get('usd', 0.0)
            total_volume = market_data.get('total_volume', {}).get('usd', 0.0)
            
            volume_ratio = (total_volume / market_cap * 100) if market_cap > 0 else 0.0
            
            score = 50
            
            if price_24h > 5: score += 15
            elif price_24h > 0: score += 5
            elif price_24h < -10: score -= 20
            elif price_24h < -5: score -= 10
            
            if price_7d > 10: score += 10
            elif price_7d > 0: score += 3
            elif price_7d < -15: score -= 15
            elif price_7d < -5: score -= 8
            
            if price_30d > 20: score += 8
            elif price_30d < -30: score -= 12
            
            if market_cap_rank <= 10: score += 10
            elif market_cap_rank <= 50: score += 5
            elif market_cap_rank > 200: score -= 5
            
            if volume_ratio > 15: score += 8
            elif volume_ratio < 2: score -= 10
            
            score = max(10, min(95, score))
            
            if score >= 75:
                recommendation = "STRONG BUY"
                color = Colors.BRIGHT_GREEN + Colors.BOLD
            elif score >= 60:
                recommendation = "BUY"
                color = Colors.BRIGHT_GREEN
            elif score >= 40:
                recommendation = "HOLD"
                color = Colors.BRIGHT_YELLOW
            elif score >= 25:
                recommendation = "WAIT"
                color = Colors.BRIGHT_YELLOW + Colors.DIM
            else:
                recommendation = "AVOID"
                color = Colors.BRIGHT_RED + Colors.BOLD
            
            return {
                'recommendation': recommendation, 'confidence': score, 'color': color,
                'price_24h': price_24h, 'price_7d': price_7d, 'volume_ratio': volume_ratio
            }
            
        except KeyError as ke:
            print(f"{Colors.RED}[-] Data Structure Error: Missing expected market data key '{ke}'. Analysis skipped.{Colors.END}")
            return {'recommendation': 'DATA INCOMPLETE', 'confidence': 0, 'color': Colors.RED,
                    'price_24h': 0, 'price_7d': 0, 'volume_ratio': 0}
        except Exception as e:
            print(f"{Colors.RED}[-] Error during signal calculation: {str(e)}. Analysis skipped.{Colors.END}")
            return {'recommendation': 'ERROR', 'confidence': 0, 'color': Colors.RED,
                    'price_24h': 0, 'price_7d': 0, 'volume_ratio': 0}
    
    def analyze_coin(self, coin_id):
        """
        Fetches data for a specific coin, calculates investment signals, and displays the results.
        """
        if not coin_id:
            print(f"{Colors.BRIGHT_RED}[-] Coin ID cannot be empty. Please enter a valid ID.{Colors.END}")
            return

        print(f"\n{Colors.GRAY}{'─' * 65}{Colors.END}")
        print(f"{Colors.BRIGHT_BLUE}[-] Fetching data for {coin_id.upper()}{Colors.END}")
        
        data = self.get_crypto_data(coin_id)
        
        if not data:
            print(f"{Colors.BRIGHT_RED}[-] Analysis aborted for {coin_id.upper()} due to data retrieval issues.{Colors.END}")
            return
        
        print(f"{Colors.BRIGHT_GREEN}[+] Market data synchronized for {data['name']}{Colors.END}")
        print(f"{Colors.GRAY}[-] Processing technical indicators{Colors.END}")
        
        time.sleep(0.8) # Simulate analysis time
        
        signal = self.calculate_investment_signal(data)
        
        if signal['recommendation'] in ['ERROR', 'DATA INCOMPLETE']:
            print(f"{Colors.BRIGHT_RED}[-] Analysis for {coin_id.upper()} could not be completed.{Colors.END}")
            return

        market_data = data['market_data']
        
        print(f"{Colors.BRIGHT_BLUE}[-] Computing investment signals{Colors.END}")
        time.sleep(0.3)
        print(f"{Colors.BRIGHT_GREEN}[+] Analysis completed successfully{Colors.END}")
        
        print(f"\n{Colors.GRAY}{'─' * 65}{Colors.END}")
        
        current_price = market_data['current_price'].get('usd', 'N/A')
        market_cap = market_data.get('market_cap', {}).get('usd', 0)
        volume_24h = market_data.get('total_volume', {}).get('usd', 0)
        rank = data.get('market_cap_rank', 'N/A')

        formatted_price = f"${current_price:,.4f}" if isinstance(current_price, (int, float)) else "N/A"
        formatted_market_cap = f"${market_cap:,.0f}" if market_cap > 0 else "N/A"
        formatted_volume_24h = f"${volume_24h:,.0f}" if volume_24h > 0 else "N/A"

        print(f"{Colors.BRIGHT_CYAN}[+] Asset Analysis: {Colors.BOLD}{data['name']} ({data['symbol'].upper()}){Colors.END}")
        print(f"{Colors.BRIGHT_WHITE}[*] Current Price: {formatted_price}{Colors.END}")
        print(f"{Colors.GRAY}[*] Market Rank: #{rank}{Colors.END}")
        print(f"{Colors.BRIGHT_BLUE}[*] 24h Change: {signal['price_24h']:+.2f}%{Colors.END}")
        print(f"{Colors.BRIGHT_PURPLE}[*] 7d Trend: {signal['price_7d']:+.2f}%{Colors.END}")
        print(f"{Colors.GRAY}[*] Market Cap: {formatted_market_cap}{Colors.END}")
        print(f"{Colors.GRAY}[*] 24h Volume: {formatted_volume_24h}{Colors.END}")
        print(f"{Colors.GRAY}[*] Volume/MCap Ratio: {signal['volume_ratio']:.2f}%{Colors.END}")
        
        print(f"\n{Colors.GRAY}{'─' * 65}{Colors.END}")
        print(f"{signal['color']}[+] Investment Signal: {signal['recommendation']}{Colors.END}")
        print(f"{Colors.BRIGHT_GREEN}[*] Confidence Score: {signal['confidence']}/100{Colors.END}")
        
        if signal['recommendation'] == 'STRONG BUY':
            print(f"{Colors.BRIGHT_GREEN}[?] Strong bullish momentum and high liquidity detected.{Colors.END}")
        elif signal['recommendation'] == 'BUY':
            print(f"{Colors.BRIGHT_BLUE}[?] Positive market sentiment and upward trend indicated.{Colors.END}")
        elif signal['recommendation'] == 'HOLD':
            print(f"{Colors.BRIGHT_YELLOW}[?] Neutral signals - monitor market trends closely.{Colors.END}")
        elif signal['recommendation'] == 'WAIT':
            print(f"{Colors.BRIGHT_YELLOW}[?] Bearish indicators present. Consider waiting for clearer signals.{Colors.END}")
        else: # AVOID or ERROR
            print(f"{Colors.BRIGHT_RED}[?] High volatility, low liquidity, or significant bearish pressure detected.{Colors.END}")
        
        self.analysis_count += 1
    
    def get_popular_coins(self):
        """
        Fetches a list of popular cryptocurrencies by market capitalization.
        Returns a list of coin dictionaries on success, empty list otherwise.
        """
        self._enforce_rate_limit()
        try:
            url = f"{self.base_url}/coins/markets"
            params = {
                'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 20,
                'page': 1, 'sparkline': 'false', 'price_change_percentage': '24h,7d'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"{Colors.BRIGHT_RED}[-] Error: Rate limit exceeded for popular coins. Please wait.{Colors.END}")
            else:
                print(f"{Colors.BRIGHT_RED}[-] API Error: Could not retrieve popular coins (Status: {response.status_code}).{Colors.END}")
            return []
        except requests.exceptions.Timeout:
            print(f"{Colors.BRIGHT_RED}[-] Network Error: Request timed out while fetching popular coins.{Colors.END}")
            return []
        except requests.exceptions.ConnectionError:
            print(f"{Colors.BRIGHT_RED}[-] Network Error: Could not connect to CoinGecko API. Check internet.{Colors.END}")
            return []
        except json.JSONDecodeError:
            print(f"{Colors.BRIGHT_RED}[-] Data Error: Failed to decode JSON response for popular coins.{Colors.END}")
            return []
        except Exception as e:
            print(f"{Colors.RED}[-] An unexpected error occurred while fetching popular coins: {str(e)}{Colors.END}")
            return []
    
    def show_popular_coins(self):
        """Displays a formatted list of the top 20 cryptocurrencies."""
        print(f"{Colors.GRAY}[-] Connecting to market data feed{Colors.END}")
        coins = self.get_popular_coins()
        
        if not coins:
            print(f"{Colors.BRIGHT_RED}[-] Unable to fetch market data. Display aborted.{Colors.END}")
            return
        
        print(f"{Colors.BRIGHT_GREEN}[+] Market data synchronized{Colors.END}")
        print(f"\n{Colors.BRIGHT_CYAN}{Colors.BOLD}Top 20 Cryptocurrencies by Market Capitalization{Colors.END}\n")
        
        print(f"{Colors.BOLD}{'#':<4} {'Coin':<15} {'Price (USD)':<15} {'24h % Chg':<12} {'7d % Chg':<12} {'Market Cap':<15}{Colors.END}")
        print(f"{Colors.GRAY}{'-'*75}{Colors.END}")

        for i, coin in enumerate(coins[:20], 1):
            name = coin.get('name', 'N/A')
            symbol = coin.get('symbol', 'N/A').upper()
            current_price = coin.get('current_price', 0.0)
            price_change_24h = coin.get('price_change_percentage_24h', 0.0)
            price_change_7d = coin.get('price_change_percentage_7d_in_currency', 0.0)
            market_cap = coin.get('market_cap', 0)

            price_color_24h = Colors.BRIGHT_GREEN if price_change_24h > 0 else Colors.BRIGHT_RED if price_change_24h < 0 else Colors.WHITE
            price_color_7d = Colors.BRIGHT_GREEN if price_change_7d > 0 else Colors.BRIGHT_RED if price_change_7d < 0 else Colors.WHITE

            formatted_price = f"${current_price:,.4f}"
            formatted_market_cap = f"${market_cap:,.0f}" if market_cap > 0 else "N/A"

            print(f"{Colors.BRIGHT_BLUE}{i:<4}{Colors.BOLD}{name:<15}{Colors.END} {formatted_price:<15} "
                  f"{price_color_24h}{price_change_24h:+.2f}%{Colors.END}{' ':<1} "
                  f"{price_color_7d}{price_change_7d:+.2f}%{Colors.END}{' ':<1} "
                  f"{Colors.GRAY}{formatted_market_cap:<15}{Colors.END}")
            print()
            
    def interactive_menu(self):
        """Manages the main interactive menu for the application."""
        while True:
            print(f"\n{Colors.GRAY}{'─' * 50}{Colors.END}")
            print(f"{Colors.BRIGHT_CYAN}[?] CryptoScope Analysis Options:{Colors.END}")
            print(f"{Colors.BRIGHT_WHITE}[1] Analyze specific cryptocurrency{Colors.END}")
            print(f"{Colors.BRIGHT_WHITE}[2] View top 20 market leaders{Colors.END}")
            print(f"{Colors.BRIGHT_WHITE}[3] Quick scan (BTC, ETH, ADA){Colors.END}")
            print(f"{Colors.BRIGHT_WHITE}[4] Exit application{Colors.END}")
            
            choice = input(f"\n{Colors.BRIGHT_BLUE}[>] Select option (1-4): {Colors.END}").strip()
            
            if choice == '1':
                coin = input(f"{Colors.BRIGHT_CYAN}[>] Enter coin identifier (e.g., bitcoin, ethereum, bitcoin-cash): {Colors.END}").strip().lower()
                if coin:
                    self.analyze_coin(coin)
                else:
                    print(f"{Colors.BRIGHT_RED}[-] Coin identifier cannot be empty.{Colors.END}")
                
            elif choice == '2':
                self.show_popular_coins()
                
            elif choice == '3':
                print(f"\n{Colors.BRIGHT_BLUE}[-] Initiating quick market scan for Bitcoin, Ethereum, and Cardano.{Colors.END}")
                quick_coins = ['bitcoin', 'ethereum', 'cardano']
                for coin in quick_coins:
                    self.analyze_coin(coin)
                    if coin != quick_coins[-1]:
                        time.sleep(1.5)
                
            elif choice == '4':
                print(f"\n{Colors.GRAY}{'─' * 50}{Colors.END}")
                print(f"{Colors.BRIGHT_GREEN}[+] Session completed - {self.analysis_count} analyses performed.{Colors.END}")
                print(f"{Colors.BRIGHT_BLUE}[!] Thank you for using CryptoScope!{Colors.END}")
                break
                
            else:
                print(f"{Colors.BRIGHT_RED}[-] Invalid selection. Please choose a number between 1 and 4.{Colors.END}")
    
    def run(self):
        """Starts the CryptoScope application."""
        self.print_banner()
        
        print(f"{Colors.GREEN}[+] CryptoScope platform initialized.{Colors.END}")
        print(f"{Colors.GRAY}[*] Data provider: CoinGecko Market API{Colors.END}")
        print(f"{Colors.BLUE}[-] Loading analysis modules...{Colors.END}")
        
        time.sleep(1.2)
        
        print(f"{Colors.GREEN}[+] System ready for market analysis.{Colors.END}")
        
        self.interactive_menu()

def main():
    """Main function to run the CryptoScope application."""
    scope = CryptoScope()
    try:
        scope.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.GRAY}[-] Session terminated by user.{Colors.END}")
        print(f"{Colors.BLUE}[!] Goodbye from CryptoScope!{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.BRIGHT_RED}[-] An unhandled system error occurred: {str(e)}{Colors.END}")
        print(f"{Colors.BRIGHT_RED}[!] Please report this issue or try restarting the application.{Colors.END}")

if __name__ == "__main__":
    main()