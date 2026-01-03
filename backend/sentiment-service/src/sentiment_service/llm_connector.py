from huggingface_hub import InferenceClient

class FinbertClient:
    def __init__(
        self,
        output_file_path = "./finbert_result_test.json"
    ):
        self.output_file_path = output_file_path
        self.client = InferenceClient(
            provider="auto",
            api_key='<apiKey>',
        )
    
    def run(self):
        print(f"start the operation of {self.__class__.__name__}")
        texts = self.read_results_str()

        final_result = dict()

        id = 0
        for text in texts[:20]:
            id += 1
            print(f"working on {id}...")
            final_result[id] = dict()
            final_result[id]["text"] = text
            final_result[id]["result"] = self.lets_do_it(text)
            print(f"done with {id}!!!")

        print(f"Done with the operation of {self.__class__.__name__}: {final_result}")
        
        self.write_texts_to_file(final_result)

    def read_results_str(self,):
        with open("./filtering-results-str.txt", 'r') as f:
            d = f.readlines()
        return d

    def lets_do_it(self, text):
        try:
            result = self.client.text_classification(
                text,
                model="ProsusAI/finbert",
            )
            return result
        except Exception as e:
            print(f"Error Occurred: {str(e)}")

    def write_texts_to_file(self, texts) -> None:
        import json
        with open(self.output_file_path, "w") as f:
            json.dump(texts, f, indent=4)
        return

def main():
    pass
    # fc = FinbertClient()
    # fc.run()


if __name__ == "__main__":
    main()
