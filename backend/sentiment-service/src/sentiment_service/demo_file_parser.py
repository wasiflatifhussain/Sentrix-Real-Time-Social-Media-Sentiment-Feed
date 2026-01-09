import json
from objects.objects import Event

class DemoKafkaParser:
    def __init__(
        self,
        input_file: str = "./demo_data/ticker-events-data.json"
    ):
        self.input_file_path = input_file
        return

    def read_file(self):
        res = list()
        with open(self.input_file_path, "r") as f:
            for line in f:
                data = json.loads(line)

                if isinstance(data, dict):
                    res.append(self.construct_event(data))
        
        if isinstance(res, list):
            return res
        else:
            return None

    def construct_event(self, data):
        return Event(
            id=data.get('ingestorEvent', {'eventId': '-1'}).get('eventId', '-1'),
            source=data.get('ingestorEvent', {'source'}).get('source', '-1'),
            timestamp=data.get('ingestorEvent', {'createdAtUtc': 0}).get('createdAtUtc', 0),
            metrics=data.get('ingestorEvent', {'metrics': {}}).get('metrics', {}),
            ticker=data.get('ingestorEvent', {'ticker': None}).get('ticker', None),
            content=data.get('textView', {'textNormalized': ''}).get('textNomrlaized', '').replace("None", ''),
            metadata=data.get('filterMeta', None),
        )


class DemoMongoDBParser:
    def __init__(
        self, 
        input_file: str = "./demo_data/ticker_sentiment_hourly.json"
    ):
        self.input_file_path = input_file
        return
    
    def read_file(self):
        with open(self.input_file_path, "r") as f:
            for line in f:
                data = json.loads(line)
                if isinstance(data, list):
                    return data


if __name__ == "__main__":
    dmp = DemoMongoDBParser()
    data = dmp.read_file()

    # print(data)
    # print(type(data[0]))
    for key in data[0]:
        print()
        print(f"{key} -> {data[0][key]}")
        print()