import qrcode
import io


def f():
    image = qrcode.make('Session_id - 12\n'
                        'Ряд 4 Место 4\n'
                        'Ряд 8 Место 10')

    arr = io.BytesIO()
    image.save(arr, format='PNG')

    return arr.getvalue()


print(type(f()))