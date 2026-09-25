from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
DEAD_EXCHANGE = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)

NEW_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key="payments.new",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.new.dlq",
    },
)
RETRY_QUEUE = RabbitQueue(
    "payments.new.retry",
    durable=True,
    routing_key="payments.new.retry",
    arguments={
        "x-dead-letter-exchange": "payments",
        "x-dead-letter-routing-key": "payments.new",
    },
)
DEAD_QUEUE = RabbitQueue(
    "payments.new.dlq",
    durable=True,
    routing_key="payments.new.dlq",
)


async def declare_topology(broker: RabbitBroker) -> None:
    """Создаёт обменники, рабочую очередь, очередь повтора и DLQ."""
    payments = await broker.declare_exchange(PAYMENTS_EXCHANGE)
    dead = await broker.declare_exchange(DEAD_EXCHANGE)
    new_queue = await broker.declare_queue(NEW_QUEUE)
    retry_queue = await broker.declare_queue(RETRY_QUEUE)
    dead_queue = await broker.declare_queue(DEAD_QUEUE)
    await new_queue.bind(payments, routing_key="payments.new")
    await retry_queue.bind(payments, routing_key="payments.new.retry")
    await dead_queue.bind(dead, routing_key="payments.new.dlq")
