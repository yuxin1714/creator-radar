import math
from fastapi import HTTPException


def paginated(items,page=None,page_size=20,**extra):
    if page is None:return items
    if page<1 or page_size<1 or page_size>100:raise HTTPException(status_code=422,detail='page must be positive and page_size must be between 1 and 100')
    total=len(items);pages=max(1,math.ceil(total/page_size));current=min(page,pages)
    return {'items':items[(current-1)*page_size:current*page_size],'page':current,'page_size':page_size,'total':total,'total_pages':pages,**extra}
