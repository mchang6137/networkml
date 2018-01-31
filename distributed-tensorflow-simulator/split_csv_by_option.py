import sys
import argparse
import csv
import os

def write_to_csv(args, mcsv):
    results_file = mcsv
    file_exists = os.path.isfile(results_file)
    
    args_dict = args
    headers = args_dict.keys()
    
    #print args_dict
    with open(results_file, 'a') as out:
        writer = csv.DictWriter(out, delimiter=',', lineterminator='\n',fieldnames=headers)
        if not file_exists:
            writer.writeheader()
	writer.writerow(args_dict)

def Main (args):
    parser = argparse.ArgumentParser(description="csv Splitter Arguments", fromfile_prefix_chars='@')
    parser.add_argument(
        "base_csv",
        type=str,
        action="store",
        default="csv.csv",
        help="base directory for filename")
    
    args = parser.parse_args()

    result_csv_dict = list(csv.DictReader(open(args.base_csv)))
    plaincsv = args.base_csv
    idx = plaincsv.index(".csv")
    plaincsv = plaincsv[:idx] + "_none.csv"
    multicsv = plaincsv[:idx] + "_multi.csv"
    aggcsv = plaincsv[:idx] + "_agg.csv"
    multiaggcsv = plaincsv[:idx] + "_multiagg.csv"
    for result in result_csv_dict:
        #print "{},{}".format(result["use_multicast"], result["in_network_computation"])
        if result["use_multicast"] == "1" and result["in_network_computation"] == "1":
            #print multiaggcsv
            write_to_csv(result, multiaggcsv)
        elif result["use_multicast"] == "1":
            #print multicsv
            write_to_csv(result, multicsv)
        elif result["in_network_computation"] == "1":
            #print aggcsv
            write_to_csv(result, aggcsv)
        else:
            write_to_csv(result, plaincsv)
    
if __name__ == "__main__":
    Main(sys.argv[1:])
