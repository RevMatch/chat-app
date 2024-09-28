from models.abstract_model import AbstractModel

def chat_ui(model: AbstractModel):
    def model_func(origin_func):
        async def wrapper(*args, **kwargs):
            origin_resp = await origin_func(*args, **kwargs)
            required_attrs = model.backward_compatible()
            existing_attrs = origin_resp.keys()
            if required_attrs:
                all_present = all(item in existing_attrs for item in required_attrs)
                if not all_present:
                    return {**origin_resp, '__incompatible__': True}
            return origin_resp
        return wrapper
    return model_func