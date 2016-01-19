#!/usr/bin/python

from bisect import bisect_left
from optparse import OptionParser
import json
import re

def normalize(s):
    if s is None:
        return s
    return s.lower();

class Product:
    def __init__(self, name, family, model):
        self.name = normalize(name)
        self.family = normalize(family)
        self.model = normalize(model)
        
        # Regex to find the model (whole) in a setence. The result was the same
        # by only sorrounding the model with whitespaces, but this seems more 
        # reliable (although much slower)
        self.whole_model_re = re.compile(r'(^|\b)({0})($|\b)'.format(self.model))
    
    def __repr__(self):
        return self.name

class Family:
    def __init__(self, name):
        self.name = normalize(name)
        self.products = []
    
    def add_product(self, product):
        assert isinstance(product, Product)
        self.products.append(product)

class Manufacturer:
    def __init__(self, name):
        self.name = normalize(name)
        self.products = []         # all products
        self.families = []         # families and its products
        self.orphans_products = [] # products without family
    
    def add_product(self, product):
        if not isinstance(product, Product):
            raise TypeError
        self.products.append(product)
        
        if product.family is None:
            self.orphans_products.append(product)
        else:
            # Determines the family
            normalized_family_name = normalize(product.family)
            products_family = None
            for family in self.families:
                if family.name == normalized_family_name:
                    products_family = family
                    break
            
            if products_family is None:
                # If it doesn't exist yet, create it
                products_family = Family(normalized_family_name)
                self.families.append(products_family)
            
            # Add the product to the family
            products_family.add_product(product)
    
    def __eq__(self, other):
        return self.name == other.name
    
    def __ne__(self, other):
        return self.name != other.name
    
    def __lt__(self, other):
        return self.name < other.name
    
    def __repr__(self):
        return self.name

class Matcher:
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode

    def run(self, products_file_name, listings_file_name, output_file_name):
        self.prepare_products_data(products_file_name)
        self.match_listings(listings_file_name)
        self.produce_output(output_file_name)

    def prepare_products_data(self, products_file_name):
        self.manufacturers = []
        
        with open(products_file_name, 'r') as products_file:
            for line in products_file:
                product_json = json.loads(line)
                
                # Determines the manufacturer
                normalized_manufacturer_name = normalize(product_json['manufacturer'])
                products_manufacturer = None
                for manufacturer in self.manufacturers:
                    if manufacturer.name == normalized_manufacturer_name:
                        products_manufacturer = manufacturer
                        break
                
                if products_manufacturer is None:
                    # If it doesn't exist yet, create it
                    products_manufacturer = \
                            Manufacturer(normalized_manufacturer_name)
                    self.manufacturers.append(products_manufacturer)
                
                # Add the product to the manufacturer
                product = Product(product_json['product_name'],
                                  product_json['family'] if 'family' in product_json
                                        else None,
                                  product_json['model'])
                products_manufacturer.add_product(product)

        # Due the size of the list, it's faster to sort it afterwards than using bisect
        # to insert in sorted order
        self.manufacturers.sort()
    
    def match_listings(self, listings_file_name):
        self.matches = {}

        if self.debug_mode:        
            # for debug puporse only:
            self.matches_count = 0
            self.non_matched_manufacturer = []
            self.non_matched_product = []

        with open(listings_file_name, 'r') as listings_file:
            for line in listings_file:
                listing = json.loads(line)
                normalized_manufacturer_name = normalize(listing['manufacturer'])
                normalized_listing_title = normalize(listing['title'])
                
                manufacturer = None
                
                # Finds the manufacturer. Would it be worth to use an adaptation of
                # SortedCollection instead of instantiate a Manufacturer every time?
                index = bisect_left(self.manufacturers, 
                                    Manufacturer(normalized_manufacturer_name))
                
                # Checks if there is a match
                if index < len(self.manufacturers) \
                        and normalized_manufacturer_name in self.manufacturers[index].name:
                    manufacturer = self.manufacturers[index]
                elif index > 0 and normalized_manufacturer_name in \
                        self.manufacturers[index - 1].name:
                    manufacturer = self.manufacturers[index - 1]
                
                if manufacturer is not None:
                    # Tries to find a match for the product family
                    for family in manufacturer.families:
                        if family.name in normalized_listing_title:
                            # If succedded, search in the family's products
                            if self.find_product_and_add_to_result(
                                    family.products, listing,
                                    normalized_listing_title):
                                break
                    else:
                        # If not, tries to find a match in orphans products
                        if not self.find_product_and_add_to_result(
                                    manufacturer.orphans_products, listing,
                                    normalized_listing_title) \
                                and self.debug_mode:
                            self.non_matched_product.append(listing)
                elif self.debug_mode:
                    self.non_matched_manufacturer.append(listing)
    
    def produce_output(self, output_file_name):
        with open(output_file_name, 'w') as output_file:
            for product_name in self.matches:
                output_file.write(json.dumps({
                    'product_name': product_name,
                    'listings': self.matches[product_name]
                }) + '\n')
    
    def find_product_and_add_to_result(self, products, listing, normalized_listing_title):
        for product in products:
            assert isinstance(product, Product)
            if product.whole_model_re.search(normalized_listing_title) is not None:
                if product.name not in self.matches:
                    self.matches[product.name] = [listing]
                else:
                    self.matches[product.name].append(listing)
                
                if self.debug_mode:
                    self.matches_count += 1
                
                return True
        
        return False

def main():
    parser = OptionParser()
    parser.add_option('-p', '--products', dest='products_file',
                      help='file containing the products', metavar='FILE')
    parser.add_option('-l', '--listings', dest='listings_file',
                      help='file containing the listings', metavar='FILE')
    parser.add_option('-o', '--output', dest='output_file', default='result.txt',
                      help='file where the results will be written', metavar='FILE')
    parser.add_option('-d', '--debug', dest='debug_mode', default=False,
                      help='prints some debug info', action='store_true')
    (options, args) = parser.parse_args()
    
    # runs the Matcher
    matcher = Matcher(options.debug_mode)
    matcher.run(options.products_file, 
                options.listings_file,
                options.output_file)
    
    if matcher.debug_mode:
        # prints some debug info
        print str(matcher.matches_count) + ' matches'
        print str(len(matcher.non_matched_product) \
                + len(matcher.non_matched_manufacturer)) \
              + ' listings didn\'t match any products'
        print str(len(matcher.non_matched_manufacturer)) \
              + ' listings didn\'t event matched a manufacturer'

main()
