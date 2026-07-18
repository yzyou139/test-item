lis =  [3, 1, 2, 3, 4, 1, 2]
res1 = []
for i in lis:
    if i not in res1:
        res1.append (i)
print ("方法 1 循环：", res1)
print("-"* 20)

a = dict.fromkeys(lis)
res2 = list(a)
print("方法 2字典键唯一性：", res2)

print("-"* 20)


b = set()
res3 = [x for x in lis if not (x in b or b.add(x))]
print("方法 3列表推导：",res3)