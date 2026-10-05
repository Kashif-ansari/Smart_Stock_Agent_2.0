"""Create reproducible synthetic inputs; does not write to the business database."""
from pathlib import Path
from src.services.demo import sample_sales

def main():
    folder=Path('sample_data');folder.mkdir(exist_ok=True)
    frame=sample_sales()
    frame.to_csv(folder/'synthetic_sales.csv',index=False)
    frame.head(5).to_csv(folder/'sales_template.csv',index=False)
    print('Synthetic CSV and template written to sample_data/. No real customer data is included.')

if __name__=='__main__':main()
