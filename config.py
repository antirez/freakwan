from yaml_parser import parse_yaml, rebuild_yaml

class Config:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = parse_yaml(self.read())
        self.update_callback = None

    def get(self):
        return self.data
    
    def get_plain(self):
        plain_config = {}
        for group, items in self.data['decorated'].items():
            if group not in plain_config:
                plain_config[group] = {}
            for item in items: plain_config[group][item['id']] = item['value']
        
        plain_config.update(self.data['plain'])
        return plain_config

    def read(self):
        with open(self.file_path, 'r') as f:
            return f.read()
        
    def web_update(self, updated_config):
        self.data.update({'decorated': updated_config})

        with open(self.file_path, 'w') as f:
            f.write(rebuild_yaml(self.data))

        self.data = parse_yaml(self.read())

        if self.update_callback:  # Notify if callback is set
            try:
                self.update_callback(self.get_plain())
            except Exception as e:
                print("Callback error:", e)

    def set_update_callback(self, callback_function):
        self.update_callback = callback_function