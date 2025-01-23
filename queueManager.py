import json

ready_queue = []
not_ready_queue = []

def get_queue():
    if not ready_queue and not not_ready_queue:
        return ("Queue is empty")
    else:
        return update_queue_message()

def add_to_queue(nickname):
    if nickname in ready_queue or nickname in not_ready_queue:
        return (f"{nickname} already in the queue")
    else:
        ready_queue.append(nickname)
        return (f"{nickname} added in the queue")
    
def clear_user_queue():
    ready_queue.clear()
    not_ready_queue.clear()
    return "Queue Cleared"

def remove_from_queue(nickname):
    if nickname not in ready_queue and nickname not in not_ready_queue:
        return (f"{nickname} not in the queue")
    else:
        if nickname in ready_queue:
            ready_queue.remove(nickname)
        if nickname in not_ready_queue:
            not_ready_queue.remove(nickname)
        return (f"{nickname} removed in the queue")

def react_queue(nickname):
    if nickname in ready_queue:
        not_ready_queue.append(nickname)
        ready_queue.remove(nickname)   
    elif nickname in not_ready_queue:
        ready_queue.append(nickname)
        not_ready_queue.remove(nickname)


def update_queue_message():
    # Construct the queue message content
    queue_message_content = "**Queue: \n**"
    if ready_queue:
        queue_message_content += " -> ".join(ready_queue) + "\n"
    else:
        queue_message_content += "No users in queue.\n"

    queue_message_content += '\n**With User: \n**'
    if not_ready_queue:
        queue_message_content += ' '.join([f'{i+1}. {user}' for i, user in enumerate(not_ready_queue)])
    else:
        queue_message_content += "No users currently not ready."

    queue_message_content += '\n*Please react before and after taking a user*'
    return queue_message_content

def save_queues():
    data = {
        "ready_queue": ready_queue,
        "not_ready_queue": not_ready_queue
    }
    with open("queues.json", "w") as file:
        json.dump(data, file)

def load_queues():
    global ready_queue, not_ready_queue
    try:
        with open("queues.json", "r") as file:
            data = json.load(file)
            ready_queue = data.get("ready_queue", [])
            not_ready_queue = data.get("not_ready_queue", [])
    except FileNotFoundError:
        # If the file doesn't exist, just use empty lists
        ready_queue = []
        not_ready_queue = []