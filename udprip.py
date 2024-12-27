import sys
import json
import socket
import threading
import time
#Aline
# Configurações globais
PORT = 55151
BUFFER_SIZE = 1024

class Router:
    def __init__(self, address, update_period, startup_file=None):
        self.address = address
        self.update_period = update_period
        self.routing_table = {}
        self.neighbors = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.address, PORT))
        self.running = True
        if startup_file:
            self.process_startup_file(startup_file)
        print("Is running!")
        # Inicia a thread de envio de atualizações
        threading.Thread(target=self.send_updates, daemon=True).start()
        # Inicia a thread de recepção de mensagens
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def process_startup_file(self, startup_file):
        try:
            with open(startup_file, 'r') as f:
                for line in f:
                    command = line.strip().split()
                    if command[0] == 'add':
                        self.add_neighbor(command[1], int(command[2]))
        except FileNotFoundError:
            print(f"Erro: Arquivo de inicialização '{startup_file}' não encontrado.")
        except ValueError:
            print("Erro: Formato inválido no arquivo de inicialização.")

    def add_neighbor(self, ip, weight):
        self.neighbors[ip] = weight
        self.routing_table[ip] = {'distance': weight, 'next_hop': ip}
        print(f"Vizinho {ip} adicionado com peso {weight}")

    def del_neighbor(self, ip):
        if ip in self.neighbors:
            del self.neighbors[ip]
            self.routing_table = {k: v for k, v in self.routing_table.items() if v['next_hop'] != ip}
            print(f"Vizinho {ip} removido")

    def send_updates(self):
        while self.running:
            for neighbor in self.neighbors:
                update_message = {
                    "type": "update",
                    "source": self.address,
                    "destination": neighbor,
                    "distances": {
                        dest: data['distance'] for dest, data in self.routing_table.items() if data['next_hop'] != neighbor
                    }
                }
                try:
                    self.socket.sendto(json.dumps(update_message).encode(), (neighbor, PORT))
                except Exception as e:
                    print(f"Erro ao enviar atualização para {neighbor}: {e}")
            time.sleep(self.update_period)

    def receive_messages(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(BUFFER_SIZE)
                message = json.loads(data.decode())
                self.handle_message(message)
            except json.JSONDecodeError:
                print("Erro: Mensagem recebida não é um JSON válido.")
            except Exception as e:
                print(f"Erro ao receber mensagem: {e}")

    def handle_message(self, message):
        if message['type'] == 'update':
            self.handle_update(message)
        elif message['type'] == 'data':
            self.handle_data(message)
        elif message['type'] == 'trace':
            self.handle_trace(message)

    def handle_update(self, message):
        source = message['source']
        for dest, distance in message['distances'].items():
            new_distance = self.neighbors[source] + distance
            if dest not in self.routing_table or new_distance < self.routing_table[dest]['distance']:
                self.routing_table[dest] = {'distance': new_distance, 'next_hop': source}

    def handle_data(self, message):
        if message['destination'] == self.address:
            print(f"Mensagem recebida: {message['payload']}")
        else:
            next_hop = self.routing_table.get(message['destination'], {}).get('next_hop')
            if next_hop:
                try:
                    self.socket.sendto(json.dumps(message).encode(), (next_hop, PORT))
                except Exception as e:
                    print(f"Erro ao encaminhar mensagem para {next_hop}: {e}")

    def handle_trace(self, message):
        message['routers'].append(self.address)
        if message['destination'] == self.address:
            response = {
                "type": "data",
                "source": self.address,
                "destination": message['source'],
                "payload": json.dumps(message)
            }
            try:
                self.socket.sendto(json.dumps(response).encode(), (message['source'], PORT))
            except Exception as e:
                print(f"Erro ao enviar resposta de trace para {message['source']}: {e}")
        else:
            next_hop = self.routing_table.get(message['destination'], {}).get('next_hop')
            if next_hop:
                try:
                    self.socket.sendto(json.dumps(message).encode(), (next_hop, PORT))
                except Exception as e:
                    print(f"Erro ao encaminhar trace para {next_hop}: {e}")

    def stop(self):
        self.running = False
        self.socket.close()

    def command_loop(self):
        while self.running:
            try:
                command = input().strip().split()
                if not command:
                    continue
                if command[0] == 'add':
                    self.add_neighbor(command[1], int(command[2]))
                elif command[0] == 'del':
                    self.del_neighbor(command[1])
                elif command[0] == 'trace':
                    trace_message = {
                        "type": "trace",
                        "source": self.address,
                        "destination": command[1],
                        "routers": [self.address]
                    }
                    next_hop = self.routing_table.get(command[1], {}).get('next_hop')
                    if next_hop:
                        try:
                            self.socket.sendto(json.dumps(trace_message).encode(), (next_hop, PORT))
                        except Exception as e:
                            print(f"Erro ao enviar trace para {next_hop}: {e}")
                    else:
                        print(f"Rota para {command[1]} não encontrada.")
                elif command[0] == 'quit':
                    self.stop()
            except ValueError:
                print("Erro: Comando inválido.")
            except Exception as e:
                print(f"Erro no comando: {e}")
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: ./router.py <endereço> <intervalo> [startup]")
        sys.exit(1)
    try:
        address = sys.argv[1]
        print(f"Endereço: {address}")  # Depuração do endereço
        update_period = sys.argv[2]
        print(f"Intervalo (raw): {update_period}")  # Depuração do valor do intervalo
        # Tenta converter o intervalo para float
        update_period = float(update_period)
        startup_file = sys.argv[3] if len(sys.argv) > 3 else None
        router = Router(address, update_period, startup_file)
        try:
                router.command_loop()
        except KeyboardInterrupt:
                router.stop()
    except ValueError:
        print("Erro: Intervalo de atualização deve ser um número.")
        sys.exit(1)
