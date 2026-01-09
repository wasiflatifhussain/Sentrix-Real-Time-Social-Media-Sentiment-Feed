import json
from sentiment_service.objects.objects import Event

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
                    # res.append(self.construct_event(data))
                    res.append(data)
        
        if isinstance(res, list):
            return res
        else:
            return None

    def construct_event(self, data):
        # print({data.get('ingestorEvent', {'eventId': '-1'}).get('eventId', '-1')}, "-", data.get('textView', {'textNormalized': ''}).get('textNormalized', '').replace("None", ''))
        return Event(
            id=data.get('ingestorEvent', {'eventId': '-1'}).get('eventId', '-1'),
            source=data.get('ingestorEvent', {'source'}).get('source', '-1'),
            timestamp=data.get('ingestorEvent', {'createdAtUtc': 0}).get('createdAtUtc', 0),
            metrics=data.get('ingestorEvent', {'metrics': {}}).get('metrics', {}),
            ticker=data.get('ingestorEvent', {'ticker': None}).get('ticker', None),
            content=data.get('textView', {'textNormalized': ''}).get('textNormalized', '').replace("None", ''),
            metadata=data.get('filterMeta', None),
        )

    def write_event(self, events: list[Event]):
        file_name: str = "./finbert-result.json"
        content: list[dict] = list()

        for event in events:
            content.append(
                dict(
                    id=event.id,
                    timestamp=event.timestamp,
                    source=event.source,
                    ticker=event.ticker,
                    content=event.content,
                    metrics=event.metrics,
                    metadata=event.metadata,
                    response=event.response,
                    score=event.score,
                    conf=event.conf,
                    label=event.label,
                )
            )
        with open(file_name, 'w') as f:
            f.write(json.dumps(content))

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

    print(data)