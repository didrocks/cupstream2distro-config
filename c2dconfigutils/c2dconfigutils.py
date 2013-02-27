def dict_union(result_dict, other_dict):
    for key, val in other_dict.iteritems():
        if not isinstance(val, dict):
            result_dict[key] = val
        else:
            subdict = result_dict.setdefault(key, {})
            dict_union(subdict, val)
